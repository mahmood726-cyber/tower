#!/usr/bin/env python3
"""
Event Logger - Append-only ledger with file locking and hash chaining.
Part of Tower v1.5.5 Ledger Add-on

Usage:
    python event_logger.py log --type <type> [--card <id>] [--actor <name>] [--data <json>]
    python event_logger.py query [--type <pattern>] [--card <id>] [--since <date>] [--until <date>]
    python event_logger.py verify
    python event_logger.py rotate [--force]
    python event_logger.py tail [--n <count>]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Cross-platform file locking with timeout
import time

LOCK_TIMEOUT_DEFAULT = 30  # seconds
LOCK_RETRY_INTERVAL = 0.1  # seconds

if sys.platform == "win32":
    import msvcrt

    def _lock_file(fd, timeout: float = LOCK_TIMEOUT_DEFAULT) -> bool:
        """Acquire lock with timeout. Returns True if lock acquired."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                time.sleep(LOCK_RETRY_INTERVAL)
        return False

    def _unlock_file(fd):
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock_file(fd, timeout: float = LOCK_TIMEOUT_DEFAULT) -> bool:
        """Acquire lock with timeout. Returns True if lock acquired."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (OSError, IOError):
                time.sleep(LOCK_RETRY_INTERVAL)
        return False

    def _unlock_file(fd):
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except (OSError, IOError):
            pass


class EventLogger:
    """Append-only event logger with file locking and hash chaining."""

    DEFAULT_LEDGER_PATH = "tower/control/event_ledger.jsonl"
    LOCK_TIMEOUT_SECONDS = 30
    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

    def __init__(self, ledger_path: Optional[str] = None, enable_hash_chain: bool = True):
        """Initialize the event logger.

        Args:
            ledger_path: Path to the ledger file. Defaults to tower/control/event_ledger.jsonl
            enable_hash_chain: Whether to compute and verify hash chains
        """
        self.ledger_path = Path(ledger_path or self.DEFAULT_LEDGER_PATH)
        self.lock_path = self.ledger_path.with_suffix(".lock")
        self.enable_hash_chain = enable_hash_chain

        # Ensure directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        now = datetime.now(timezone.utc)
        short_uuid = uuid.uuid4().hex[:8]
        return f"evt_{now.strftime('%Y%m%d_%H%M%S')}_{short_uuid}"

    def _compute_hash(self, event: Dict[str, Any], prev_hash: Optional[str] = None) -> str:
        """Compute SHA256 hash of an event."""
        # Create a canonical representation
        hash_input = {
            "id": event["id"],
            "timestamp": event["timestamp"],
            "type": event["type"],
            "card_id": event.get("card_id"),
            "actor": event.get("actor"),
            "data": event.get("data"),
            "prev_hash": prev_hash,
        }
        canonical = json.dumps(hash_input, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    def _get_last_hash(self) -> Optional[str]:
        """Get the hash of the last event in the ledger."""
        if not self.ledger_path.exists():
            return None

        last_line = None
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line

        if not last_line:
            return None

        try:
            event = json.loads(last_line)
            return event.get("hash")
        except json.JSONDecodeError:
            return None

    def _acquire_lock(self, timeout: float = LOCK_TIMEOUT_DEFAULT) -> int:
        """Acquire exclusive lock on the ledger file.

        Args:
            timeout: Maximum seconds to wait for lock

        Returns:
            File descriptor for the lock

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
        """
        lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        if not _lock_file(lock_fd, timeout):
            os.close(lock_fd)
            raise TimeoutError(f"Could not acquire lock within {timeout}s: {self.lock_path}")
        return lock_fd

    def _release_lock(self, lock_fd: int) -> None:
        """Release the lock.

        Note: We intentionally do NOT delete the lock file after releasing.
        Deleting the lock file creates a race condition where another process
        could create and lock a new file between our unlock and delete.
        The lock file is small and persisting it is safe - the lock is on the
        file descriptor, not the file's existence.
        """
        try:
            _unlock_file(lock_fd)
        except (OSError, IOError):
            pass
        os.close(lock_fd)

    def log(
        self,
        event_type: str,
        card_id: Optional[str] = None,
        actor: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log an event to the ledger.

        Args:
            event_type: Hierarchical event type (e.g., "card.state_change")
            card_id: Optional card ID if event relates to a card
            actor: Optional actor (script, user) that triggered the event
            data: Optional arbitrary payload

        Returns:
            The logged event
        """
        lock_fd = self._acquire_lock()
        try:
            # Check if rotation needed
            if self.ledger_path.exists() and self.ledger_path.stat().st_size > self.MAX_SIZE_BYTES:
                self._rotate_internal()

            # Get previous hash for chaining
            prev_hash = self._get_last_hash() if self.enable_hash_chain else None

            # Build event
            event = {
                "id": self._generate_event_id(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
            }

            if card_id:
                event["card_id"] = card_id
            if actor:
                event["actor"] = actor
            if data:
                event["data"] = data

            # Add hash chain
            if self.enable_hash_chain:
                if prev_hash:
                    event["prev_hash"] = prev_hash
                event["hash"] = self._compute_hash(event, prev_hash)

            # Append to ledger
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())

            return event

        finally:
            self._release_lock(lock_fd)

    def _rotate_internal(self) -> str:
        """Internal rotation (called while holding lock)."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = self.ledger_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"event_ledger_{timestamp}.jsonl"
        shutil.move(str(self.ledger_path), str(backup_path))
        return str(backup_path)

    def rotate(self, force: bool = False) -> Optional[str]:
        """Rotate the ledger file.

        Args:
            force: Rotate even if under size threshold

        Returns:
            Path to backup file, or None if no rotation occurred
        """
        if not self.ledger_path.exists():
            return None

        if not force and self.ledger_path.stat().st_size <= self.MAX_SIZE_BYTES:
            return None

        lock_fd = self._acquire_lock()
        try:
            return self._rotate_internal()
        finally:
            self._release_lock(lock_fd)

    def query(
        self,
        event_type: Optional[str] = None,
        card_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query events from the ledger.

        Args:
            event_type: Glob pattern for event type (e.g., "card.*")
            card_id: Filter by card ID
            since: ISO date string, only events after this
            until: ISO date string, only events before this
            limit: Maximum number of events to return

        Returns:
            List of matching events
        """
        if not self.ledger_path.exists():
            return []

        # Convert event_type glob to regex
        type_pattern = None
        if event_type:
            pattern = event_type.replace(".", r"\.").replace("*", ".*")
            type_pattern = re.compile(f"^{pattern}$")

        # Parse date filters
        since_dt = None
        until_dt = None
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if until:
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))

        results = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Apply filters
                if type_pattern and not type_pattern.match(event.get("type", "")):
                    continue

                if card_id and event.get("card_id") != card_id:
                    continue

                if since_dt or until_dt:
                    try:
                        event_dt = datetime.fromisoformat(
                            event["timestamp"].replace("Z", "+00:00")
                        )
                        if since_dt and event_dt < since_dt:
                            continue
                        if until_dt and event_dt > until_dt:
                            continue
                    except (ValueError, KeyError):
                        continue

                results.append(event)

                if limit and len(results) >= limit:
                    break

        return results

    def tail(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the last N events.

        Args:
            n: Number of events to return

        Returns:
            Last N events
        """
        if not self.ledger_path.exists():
            return []

        events = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                        if len(events) > n:
                            events.pop(0)
                    except json.JSONDecodeError:
                        pass

        return events

    def verify(self) -> Tuple[bool, List[str]]:
        """Verify the integrity of the ledger hash chain.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        if not self.ledger_path.exists():
            return True, []

        errors = []
        prev_hash = None
        line_num = 0

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
                    continue

                # Verify required fields
                if "id" not in event:
                    errors.append(f"Line {line_num}: Missing 'id' field")
                if "timestamp" not in event:
                    errors.append(f"Line {line_num}: Missing 'timestamp' field")
                if "type" not in event:
                    errors.append(f"Line {line_num}: Missing 'type' field")

                # Verify hash chain if enabled
                if self.enable_hash_chain and "hash" in event:
                    # Check prev_hash matches
                    if prev_hash and event.get("prev_hash") != prev_hash:
                        errors.append(
                            f"Line {line_num}: Hash chain broken - "
                            f"prev_hash mismatch for event {event.get('id')}"
                        )

                    # Verify hash computation
                    expected_hash = self._compute_hash(event, event.get("prev_hash"))
                    if event["hash"] != expected_hash:
                        errors.append(
                            f"Line {line_num}: Hash mismatch for event {event.get('id')} - "
                            f"expected {expected_hash}, got {event['hash']}"
                        )

                    prev_hash = event.get("hash")

        return len(errors) == 0, errors

    def get_state_transitions(
        self,
        card_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get state transition history for cards.

        This method queries the ledger for card state change events,
        useful for computing historical SLO metrics like rollback rates.

        Args:
            card_id: Optional card ID to filter by
            since: ISO date string, only events after this
            until: ISO date string, only events before this

        Returns:
            List of state transition events with from_state and to_state
        """
        events = self.query(
            event_type="card.state_change",
            card_id=card_id,
            since=since,
            until=until,
        )

        transitions = []
        for event in events:
            data = event.get("data", {})
            transitions.append({
                "event_id": event.get("id"),
                "timestamp": event.get("timestamp"),
                "card_id": event.get("card_id"),
                "from_state": data.get("from_state"),
                "to_state": data.get("to_state"),
                "actor": event.get("actor"),
            })

        return transitions

    def count_by_type(
        self,
        event_type: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> int:
        """Count events of a specific type within a time window.

        Args:
            event_type: Event type pattern (glob supported)
            since: ISO date string, only events after this
            until: ISO date string, only events before this

        Returns:
            Count of matching events
        """
        events = self.query(
            event_type=event_type,
            since=since,
            until=until,
        )
        return len(events)

    def get_active_hours(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> float:
        """Calculate active hours based on event activity.

        Active hours are computed as the time span during which events
        were recorded, useful for normalizing SLO metrics.

        Args:
            since: ISO date string, only events after this
            until: ISO date string, only events before this

        Returns:
            Active hours as float
        """
        events = self.query(since=since, until=until)

        if len(events) < 2:
            return 0.0

        # Get first and last event timestamps
        first_ts = events[0].get("timestamp")
        last_ts = events[-1].get("timestamp")

        if not first_ts or not last_ts:
            return 0.0

        try:
            first_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            delta = last_dt - first_dt
            return delta.total_seconds() / 3600.0
        except (ValueError, TypeError):
            return 0.0

    def stats(self) -> Dict[str, Any]:
        """Get statistics about the ledger.

        Returns:
            Dictionary with ledger statistics
        """
        if not self.ledger_path.exists():
            return {
                "exists": False,
                "events": 0,
                "size_bytes": 0,
            }

        event_count = 0
        type_counts: Dict[str, int] = {}
        first_timestamp = None
        last_timestamp = None

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    event_count += 1
                    event_type = event.get("type", "unknown")
                    type_counts[event_type] = type_counts.get(event_type, 0) + 1
                    ts = event.get("timestamp")
                    if ts:
                        if first_timestamp is None:
                            first_timestamp = ts
                        last_timestamp = ts
                except json.JSONDecodeError:
                    pass

        return {
            "exists": True,
            "events": event_count,
            "size_bytes": self.ledger_path.stat().st_size,
            "first_event": first_timestamp,
            "last_event": last_timestamp,
            "event_types": type_counts,
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Tower Event Logger")
    parser.add_argument(
        "--ledger",
        default=EventLogger.DEFAULT_LEDGER_PATH,
        help="Path to ledger file",
    )
    parser.add_argument(
        "--no-hash-chain",
        action="store_true",
        help="Disable hash chaining",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Log command
    log_parser = subparsers.add_parser("log", help="Log an event")
    log_parser.add_argument("--type", "-t", required=True, help="Event type")
    log_parser.add_argument("--card", "-c", help="Card ID")
    log_parser.add_argument("--actor", "-a", help="Actor name")
    log_parser.add_argument("--data", "-d", help="JSON data payload")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query events")
    query_parser.add_argument("--type", "-t", help="Event type pattern (glob)")
    query_parser.add_argument("--card", "-c", help="Card ID")
    query_parser.add_argument("--since", help="Events since (ISO date)")
    query_parser.add_argument("--until", help="Events until (ISO date)")
    query_parser.add_argument("--limit", "-n", type=int, help="Maximum results")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Verify command
    subparsers.add_parser("verify", help="Verify ledger integrity")

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate ledger file")
    rotate_parser.add_argument("--force", action="store_true", help="Force rotation")

    # Tail command
    tail_parser = subparsers.add_parser("tail", help="Show last N events")
    tail_parser.add_argument("-n", type=int, default=10, help="Number of events")
    tail_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show ledger statistics")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    logger = EventLogger(
        ledger_path=args.ledger,
        enable_hash_chain=not args.no_hash_chain,
    )

    if args.command == "log":
        data = None
        if args.data:
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON data: {args.data}", file=sys.stderr)
                sys.exit(1)

        event = logger.log(
            event_type=args.type,
            card_id=args.card,
            actor=args.actor,
            data=data,
        )
        print(json.dumps(event, indent=2))

    elif args.command == "query":
        events = logger.query(
            event_type=args.type,
            card_id=args.card,
            since=args.since,
            until=args.until,
            limit=args.limit,
        )

        if args.json:
            print(json.dumps(events, indent=2))
        else:
            for event in events:
                ts = event.get("timestamp", "?")[:19]
                etype = event.get("type", "?")
                card = event.get("card_id", "-")
                print(f"{ts}  {etype:<30}  {card}")

    elif args.command == "verify":
        print("Verifying ledger integrity...")
        is_valid, errors = logger.verify()
        stats = logger.stats()

        print(f"  Events checked: {stats.get('events', 0)}")
        if is_valid:
            print("  Hash chain: VALID")
        else:
            print("  Hash chain: BROKEN")
            for err in errors[:10]:
                print(f"    - {err}")
            if len(errors) > 10:
                print(f"    ... and {len(errors) - 10} more errors")

        print(f"  First event: {stats.get('first_event', 'N/A')}")
        print(f"  Last event: {stats.get('last_event', 'N/A')}")
        print(f"  Status: {'OK' if is_valid else 'COMPROMISED'}")
        sys.exit(0 if is_valid else 1)

    elif args.command == "rotate":
        backup = logger.rotate(force=args.force)
        if backup:
            print(f"Rotated to: {backup}")
        else:
            print("No rotation needed (under size threshold)")

    elif args.command == "tail":
        events = logger.tail(n=args.n)
        if args.json:
            print(json.dumps(events, indent=2))
        else:
            for event in events:
                ts = event.get("timestamp", "?")[:19]
                etype = event.get("type", "?")
                card = event.get("card_id", "-")
                data = json.dumps(event.get("data", {}))[:50]
                print(f"{ts}  {etype:<25}  {card:<12}  {data}")

    elif args.command == "stats":
        stats = logger.stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Ledger: {args.ledger}")
            print(f"Exists: {stats.get('exists', False)}")
            print(f"Events: {stats.get('events', 0)}")
            print(f"Size: {stats.get('size_bytes', 0) / 1024:.1f} KB")
            print(f"First: {stats.get('first_event', 'N/A')}")
            print(f"Last: {stats.get('last_event', 'N/A')}")
            if stats.get("event_types"):
                print("Event types:")
                for etype, count in sorted(
                    stats["event_types"].items(), key=lambda x: -x[1]
                )[:10]:
                    print(f"  {etype}: {count}")


# ============================================================================
# Module-level convenience functions for integration with other addons
# ============================================================================

_default_logger: Optional[EventLogger] = None


def _get_default_logger(ledger_path: Optional[str] = None) -> EventLogger:
    """Get or create the default logger instance."""
    global _default_logger
    if ledger_path:
        return EventLogger(ledger_path=ledger_path)
    if _default_logger is None:
        _default_logger = EventLogger()
    return _default_logger


def log_event(
    event: Dict[str, Any],
    ledger_path: Optional[str] = None
) -> bool:
    """Log an event to the ledger.

    Args:
        event: Event dict with event_type, card_id, details, etc.
        ledger_path: Optional custom ledger path

    Returns:
        True if successful
    """
    try:
        logger = _get_default_logger(ledger_path)
        logger.log(
            event_type=event.get("event_type", "UNKNOWN"),
            card_id=event.get("card_id"),
            actor=event.get("actor"),
            data=event.get("details", event.get("data"))
        )
        return True
    except Exception as e:
        print(f"[ledger] Failed to log event: {e}", file=sys.stderr)
        return False


def read_events(
    ledger_path: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Read events from the ledger.

    Args:
        ledger_path: Optional custom ledger path
        limit: Maximum number of events to return

    Returns:
        List of events
    """
    logger = _get_default_logger(ledger_path)
    return logger.query(limit=limit)


def verify_chain(ledger_path: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Verify the integrity of the ledger hash chain.

    Args:
        ledger_path: Optional custom ledger path

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    logger = _get_default_logger(ledger_path)
    return logger.verify()


def get_state_transitions(
    card_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    ledger_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get state transition history for cards.

    Args:
        card_id: Optional card ID to filter by
        since: ISO date string, only events after this
        until: ISO date string, only events before this
        ledger_path: Optional custom ledger path

    Returns:
        List of state transition events
    """
    logger = _get_default_logger(ledger_path)
    return logger.get_state_transitions(card_id=card_id, since=since, until=until)


def count_events_by_type(
    event_type: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    ledger_path: Optional[str] = None,
) -> int:
    """Count events of a specific type within a time window.

    Args:
        event_type: Event type pattern (glob supported)
        since: ISO date string, only events after this
        until: ISO date string, only events before this
        ledger_path: Optional custom ledger path

    Returns:
        Count of matching events
    """
    logger = _get_default_logger(ledger_path)
    return logger.count_by_type(event_type=event_type, since=since, until=until)


def get_active_hours(
    since: Optional[str] = None,
    until: Optional[str] = None,
    ledger_path: Optional[str] = None,
) -> float:
    """Calculate active hours based on event activity.

    Args:
        since: ISO date string, only events after this
        until: ISO date string, only events before this
        ledger_path: Optional custom ledger path

    Returns:
        Active hours as float
    """
    logger = _get_default_logger(ledger_path)
    return logger.get_active_hours(since=since, until=until)


if __name__ == "__main__":
    main()
