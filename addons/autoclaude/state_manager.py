#!/usr/bin/env python3
"""
State Manager for Crash Recovery

Provides unified state management with:
- Atomic multi-file state snapshots
- WAL-style journaling for crash recovery
- State version migration support
- Periodic backup scheduling
- Rollback capabilities
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOWER_ROOT = SCRIPT_DIR.parent.parent
LEDGER_DIR = TOWER_ROOT / "addons" / "ledger"

# Import event logger
sys.path.insert(0, str(LEDGER_DIR))
try:
    from event_logger import EventLogger
    LEDGER_AVAILABLE = True
except ImportError:
    LEDGER_AVAILABLE = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class StateStatus(Enum):
    """Status of a state snapshot."""
    PENDING = "pending"       # Being created
    COMPLETE = "complete"     # Successfully saved
    CORRUPTED = "corrupted"   # Failed verification
    RECOVERED = "recovered"   # Recovered from WAL


class OperationType(Enum):
    """Types of state operations for WAL."""
    SET = "set"
    DELETE = "delete"
    UPDATE = "update"
    CHECKPOINT = "checkpoint"


@dataclass
class WALEntry:
    """Write-ahead log entry."""

    sequence: int
    operation: OperationType
    namespace: str
    key: str
    value: Optional[Any] = None
    timestamp: str = field(default_factory=lambda: _now_utc().isoformat())
    checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["operation"] = self.operation.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WALEntry":
        return cls(
            sequence=d["sequence"],
            operation=OperationType(d["operation"]),
            namespace=d["namespace"],
            key=d["key"],
            value=d.get("value"),
            timestamp=d.get("timestamp", _now_utc().isoformat()),
            checksum=d.get("checksum"),
        )

    def compute_checksum(self) -> str:
        """Compute checksum for integrity verification."""
        data = f"{self.sequence}:{self.operation.value}:{self.namespace}:{self.key}:{json.dumps(self.value, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class Snapshot:
    """A complete state snapshot."""

    snapshot_id: str
    version: int
    timestamp: str
    namespaces: Dict[str, Dict[str, Any]]
    status: StateStatus = StateStatus.PENDING
    checksum: Optional[str] = None
    wal_sequence: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Snapshot":
        return cls(
            snapshot_id=d["snapshot_id"],
            version=d["version"],
            timestamp=d["timestamp"],
            namespaces=d["namespaces"],
            status=StateStatus(d.get("status", "complete")),
            checksum=d.get("checksum"),
            wal_sequence=d.get("wal_sequence", 0),
            metadata=d.get("metadata", {}),
        )

    def compute_checksum(self) -> str:
        """Compute checksum for snapshot integrity."""
        data = json.dumps(self.namespaces, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class StateConfig:
    """Configuration for state manager."""

    wal_enabled: bool = True
    max_wal_entries: int = 10000
    snapshot_interval_seconds: int = 300  # 5 minutes
    max_snapshots: int = 10
    compression: bool = False
    encryption: bool = False


class StateCorruptionError(Exception):
    """Raised when state corruption is detected."""

    def __init__(self, message: str, snapshot_id: Optional[str] = None):
        self.snapshot_id = snapshot_id
        super().__init__(message)


class StateManager:
    """
    Manages agent state with crash recovery.

    Features:
    - Namespaced key-value storage
    - Write-ahead logging for durability
    - Atomic snapshots
    - Automatic recovery
    - Version migration
    """

    CURRENT_VERSION = 1

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        config: Optional[StateConfig] = None,
        ledger: Optional[EventLogger] = None,
        migration_handlers: Optional[Dict[int, Callable[[Dict], Dict]]] = None,
    ):
        """
        Initialize state manager.

        Args:
            storage_path: Directory for state storage
            config: State configuration
            ledger: Optional EventLogger
            migration_handlers: Version migration functions
        """
        self.storage_path = storage_path or (TOWER_ROOT / "control" / "state")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.config = config or StateConfig()
        self.ledger = ledger
        self.migration_handlers = migration_handlers or {}

        # State storage
        self._namespaces: Dict[str, Dict[str, Any]] = {}
        self._wal: List[WALEntry] = []
        self._wal_sequence = 0
        self._lock = threading.RLock()

        # Paths
        self._wal_path = self.storage_path / "wal.jsonl"
        self._snapshot_dir = self.storage_path / "snapshots"
        self._snapshot_dir.mkdir(exist_ok=True)

        # Initialize
        self._recover_state()

        # Background snapshot thread
        self._snapshot_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _log_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Log state event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"state.{event_type}",
                card_id=None,
                actor="state_manager",
                data=data,
            )

    def _write_wal(self, entry: WALEntry) -> None:
        """Write entry to WAL."""
        if not self.config.wal_enabled:
            return

        entry.checksum = entry.compute_checksum()

        with open(self._wal_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())

        self._wal.append(entry)

        # Truncate WAL if too large
        if len(self._wal) > self.config.max_wal_entries:
            self._create_snapshot()
            self._truncate_wal()

    def _truncate_wal(self) -> None:
        """Truncate WAL after snapshot."""
        self._wal.clear()
        if self._wal_path.exists():
            self._wal_path.unlink()

    def _recover_state(self) -> None:
        """Recover state from snapshot and WAL."""
        # Load latest snapshot
        snapshot = self._load_latest_snapshot()

        if snapshot:
            self._namespaces = snapshot.namespaces.copy()
            self._wal_sequence = snapshot.wal_sequence

            self._log_event("snapshot_loaded", {
                "snapshot_id": snapshot.snapshot_id,
                "version": snapshot.version,
            })

        # Replay WAL
        if self.config.wal_enabled and self._wal_path.exists():
            self._replay_wal()

    def _load_latest_snapshot(self) -> Optional[Snapshot]:
        """Load the most recent valid snapshot."""
        snapshots = sorted(
            self._snapshot_dir.glob("snapshot_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for snapshot_path in snapshots:
            try:
                with open(snapshot_path) as f:
                    data = json.load(f)

                snapshot = Snapshot.from_dict(data)

                # Verify checksum
                if snapshot.checksum and snapshot.compute_checksum() != snapshot.checksum:
                    self._log_event("snapshot_corrupted", {
                        "snapshot_id": snapshot.snapshot_id,
                    })
                    continue

                # Migrate if needed
                if snapshot.version < self.CURRENT_VERSION:
                    snapshot = self._migrate_snapshot(snapshot)

                return snapshot

            except (json.JSONDecodeError, KeyError) as e:
                self._log_event("snapshot_load_failed", {
                    "path": str(snapshot_path),
                    "error": str(e),
                })
                continue

        return None

    def _migrate_snapshot(self, snapshot: Snapshot) -> Snapshot:
        """Migrate snapshot to current version."""
        current_version = snapshot.version

        while current_version < self.CURRENT_VERSION:
            if current_version in self.migration_handlers:
                handler = self.migration_handlers[current_version]
                snapshot.namespaces = handler(snapshot.namespaces)

            current_version += 1

        snapshot.version = self.CURRENT_VERSION

        self._log_event("snapshot_migrated", {
            "snapshot_id": snapshot.snapshot_id,
            "from_version": snapshot.version,
            "to_version": self.CURRENT_VERSION,
        })

        return snapshot

    def _replay_wal(self) -> None:
        """Replay WAL entries to recover state."""
        if not self._wal_path.exists():
            return

        replayed = 0
        skipped = 0

        with open(self._wal_path) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    entry = WALEntry.from_dict(data)

                    # Skip entries before our sequence
                    if entry.sequence <= self._wal_sequence:
                        skipped += 1
                        continue

                    # Verify checksum
                    if entry.checksum and entry.compute_checksum() != entry.checksum:
                        self._log_event("wal_entry_corrupted", {
                            "sequence": entry.sequence,
                        })
                        continue

                    # Apply entry
                    self._apply_wal_entry(entry)
                    self._wal.append(entry)
                    self._wal_sequence = entry.sequence
                    replayed += 1

                except (json.JSONDecodeError, KeyError):
                    continue

        if replayed > 0:
            self._log_event("wal_replayed", {
                "replayed": replayed,
                "skipped": skipped,
            })

    def _apply_wal_entry(self, entry: WALEntry) -> None:
        """Apply a single WAL entry to state."""
        if entry.namespace not in self._namespaces:
            self._namespaces[entry.namespace] = {}

        ns = self._namespaces[entry.namespace]

        if entry.operation == OperationType.SET:
            ns[entry.key] = entry.value
        elif entry.operation == OperationType.DELETE:
            ns.pop(entry.key, None)
        elif entry.operation == OperationType.UPDATE:
            if entry.key in ns and isinstance(ns[entry.key], dict) and isinstance(entry.value, dict):
                ns[entry.key].update(entry.value)
            else:
                ns[entry.key] = entry.value

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Set a value in state.

        Args:
            namespace: State namespace
            key: Key within namespace
            value: Value to store
        """
        with self._lock:
            self._wal_sequence += 1

            entry = WALEntry(
                sequence=self._wal_sequence,
                operation=OperationType.SET,
                namespace=namespace,
                key=key,
                value=value,
            )

            self._write_wal(entry)
            self._apply_wal_entry(entry)

    def get(
        self,
        namespace: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a value from state.

        Args:
            namespace: State namespace
            key: Key within namespace
            default: Default value if not found

        Returns:
            The stored value or default
        """
        with self._lock:
            ns = self._namespaces.get(namespace, {})
            return ns.get(key, default)

    def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a value from state.

        Returns True if key existed.
        """
        with self._lock:
            self._wal_sequence += 1

            entry = WALEntry(
                sequence=self._wal_sequence,
                operation=OperationType.DELETE,
                namespace=namespace,
                key=key,
            )

            existed = key in self._namespaces.get(namespace, {})
            self._write_wal(entry)
            self._apply_wal_entry(entry)

            return existed

    def update(
        self,
        namespace: str,
        key: str,
        updates: Dict[str, Any],
    ) -> None:
        """
        Update a dictionary value (merge).

        Args:
            namespace: State namespace
            key: Key within namespace
            updates: Dictionary of updates to merge
        """
        with self._lock:
            self._wal_sequence += 1

            entry = WALEntry(
                sequence=self._wal_sequence,
                operation=OperationType.UPDATE,
                namespace=namespace,
                key=key,
                value=updates,
            )

            self._write_wal(entry)
            self._apply_wal_entry(entry)

    def get_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get all values in a namespace."""
        with self._lock:
            return self._namespaces.get(namespace, {}).copy()

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        with self._lock:
            return list(self._namespaces.keys())

    def clear_namespace(self, namespace: str) -> None:
        """Clear all values in a namespace."""
        with self._lock:
            if namespace in self._namespaces:
                for key in list(self._namespaces[namespace].keys()):
                    self.delete(namespace, key)

    def _create_snapshot(self) -> Snapshot:
        """Create a state snapshot."""
        with self._lock:
            timestamp = _now_utc().isoformat()
            snapshot_id = f"snapshot_{timestamp.replace(':', '-').replace('.', '-')}"

            snapshot = Snapshot(
                snapshot_id=snapshot_id,
                version=self.CURRENT_VERSION,
                timestamp=timestamp,
                namespaces={k: v.copy() for k, v in self._namespaces.items()},
                status=StateStatus.PENDING,
                wal_sequence=self._wal_sequence,
            )

            snapshot.checksum = snapshot.compute_checksum()
            snapshot.status = StateStatus.COMPLETE

            # Write snapshot
            snapshot_path = self._snapshot_dir / f"{snapshot_id}.json"
            temp_path = snapshot_path.with_suffix(".tmp")

            with open(temp_path, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            temp_path.replace(snapshot_path)

            # Cleanup old snapshots
            self._cleanup_old_snapshots()

            self._log_event("snapshot_created", {
                "snapshot_id": snapshot_id,
                "namespaces": len(snapshot.namespaces),
                "wal_sequence": snapshot.wal_sequence,
            })

            return snapshot

    def _cleanup_old_snapshots(self) -> None:
        """Remove old snapshots beyond max_snapshots."""
        snapshots = sorted(
            self._snapshot_dir.glob("snapshot_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for snapshot_path in snapshots[self.config.max_snapshots:]:
            snapshot_path.unlink()

    def create_checkpoint(self, label: Optional[str] = None) -> str:
        """
        Create a named checkpoint.

        Returns checkpoint ID.
        """
        snapshot = self._create_snapshot()

        if label:
            snapshot.metadata["label"] = label

        # Also truncate WAL
        self._truncate_wal()

        return snapshot.snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """
        Rollback to a specific snapshot.

        Args:
            snapshot_id: Snapshot to rollback to

        Returns:
            True if rollback succeeded
        """
        snapshot_path = self._snapshot_dir / f"{snapshot_id}.json"

        if not snapshot_path.exists():
            return False

        try:
            with open(snapshot_path) as f:
                data = json.load(f)

            snapshot = Snapshot.from_dict(data)

            # Verify checksum
            if snapshot.checksum and snapshot.compute_checksum() != snapshot.checksum:
                raise StateCorruptionError("Snapshot checksum mismatch", snapshot_id)

            with self._lock:
                self._namespaces = snapshot.namespaces.copy()
                self._wal_sequence = snapshot.wal_sequence
                self._truncate_wal()

            self._log_event("rollback", {
                "snapshot_id": snapshot_id,
            })

            return True

        except (json.JSONDecodeError, KeyError) as e:
            self._log_event("rollback_failed", {
                "snapshot_id": snapshot_id,
                "error": str(e),
            })
            return False

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots."""
        snapshots = []

        for path in self._snapshot_dir.glob("snapshot_*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)

                snapshots.append({
                    "snapshot_id": data["snapshot_id"],
                    "timestamp": data["timestamp"],
                    "version": data["version"],
                    "status": data.get("status", "complete"),
                    "namespace_count": len(data.get("namespaces", {})),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(snapshots, key=lambda s: s["timestamp"], reverse=True)

    def start_background_snapshots(self) -> None:
        """Start background snapshot thread."""
        if self._snapshot_thread and self._snapshot_thread.is_alive():
            return

        self._stop_event.clear()

        def snapshot_loop():
            while not self._stop_event.wait(self.config.snapshot_interval_seconds):
                try:
                    self._create_snapshot()
                except Exception as e:
                    self._log_event("snapshot_error", {"error": str(e)})

        self._snapshot_thread = threading.Thread(target=snapshot_loop, daemon=True)
        self._snapshot_thread.start()

    def stop_background_snapshots(self) -> None:
        """Stop background snapshot thread."""
        self._stop_event.set()
        if self._snapshot_thread:
            self._snapshot_thread.join(timeout=5)

    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        with self._lock:
            total_keys = sum(len(ns) for ns in self._namespaces.values())

            return {
                "namespaces": len(self._namespaces),
                "total_keys": total_keys,
                "wal_entries": len(self._wal),
                "wal_sequence": self._wal_sequence,
                "snapshots": len(list(self._snapshot_dir.glob("snapshot_*.json"))),
            }


# Convenience functions
def create_state_manager(
    ledger: Optional[EventLogger] = None,
) -> StateManager:
    """Create a state manager with default configuration."""
    return StateManager(ledger=ledger)
