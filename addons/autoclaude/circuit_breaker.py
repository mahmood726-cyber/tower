#!/usr/bin/env python3
"""
Circuit Breaker for LLM Agent Loops

Prevents runaway correction loops with:
- Configurable failure thresholds
- Automatic state transitions (CLOSED -> OPEN -> HALF_OPEN)
- Per-card tracking
- Escalation triggers
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOWER_ROOT = SCRIPT_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
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


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation, failures tracked
    OPEN = "OPEN"          # Tripped, rejecting all calls
    HALF_OPEN = "HALF_OPEN"  # Testing if system recovered


class CircuitOpenError(Exception):
    """Raised when circuit is open and call is rejected."""

    def __init__(self, card_id: str, failure_count: int, message: str = ""):
        self.card_id = card_id
        self.failure_count = failure_count
        super().__init__(message or f"Circuit open for {card_id} after {failure_count} failures")


@dataclass
class CircuitStatus:
    """Status of a circuit breaker."""
    card_id: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[str]
    last_success_time: Optional[str]
    opened_at: Optional[str]
    half_open_at: Optional[str]
    total_rejections: int

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 2          # Successes to close from half-open
    reset_timeout_seconds: int = 300    # Time before attempting half-open (5 min)
    half_open_max_calls: int = 3        # Max calls allowed in half-open state

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CircuitBreaker:
    """
    Circuit breaker for preventing runaway LLM correction loops.

    Features:
    - Per-card circuit tracking
    - Configurable failure/success thresholds
    - Automatic state transitions
    - Escalation callbacks
    - Persistence across restarts
    """

    def __init__(
        self,
        config: Optional[CircuitConfig] = None,
        state_path: Optional[str] = None,
        on_open: Optional[Callable[[str, int], None]] = None,
        on_close: Optional[Callable[[str], None]] = None,
        on_escalate: Optional[Callable[[str, int], None]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
            state_path: Path to persist circuit states
            on_open: Callback when circuit opens (card_id, failure_count)
            on_close: Callback when circuit closes (card_id)
            on_escalate: Callback for escalation (card_id, failure_count)
            ledger: Optional EventLogger for integrated logging
        """
        self.config = config or CircuitConfig()

        if state_path:
            self.state_path = Path(state_path)
        else:
            self.state_path = CONTROL_DIR / "circuit_states.json"

        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self.on_open = on_open
        self.on_close = on_close
        self.on_escalate = on_escalate
        self.ledger = ledger

        # Load persisted state
        self._circuits: Dict[str, CircuitStatus] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted circuit states."""
        if not self.state_path.exists():
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for card_id, status_data in data.get("circuits", {}).items():
                status_data["state"] = CircuitState(status_data["state"])
                self._circuits[card_id] = CircuitStatus(**status_data)
        except (json.JSONDecodeError, KeyError, TypeError):
            self._circuits = {}

    def _save_state(self) -> None:
        """Persist circuit states."""
        data = {
            "last_updated": _now_utc().isoformat(),
            "config": self.config.to_dict(),
            "circuits": {
                card_id: status.to_dict()
                for card_id, status in self._circuits.items()
            },
        }

        tmp_path = self.state_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.state_path)

    def _get_or_create_circuit(self, card_id: str) -> CircuitStatus:
        """Get or create circuit status for a card."""
        if card_id not in self._circuits:
            self._circuits[card_id] = CircuitStatus(
                card_id=card_id,
                state=CircuitState.CLOSED,
                failure_count=0,
                success_count=0,
                last_failure_time=None,
                last_success_time=None,
                opened_at=None,
                half_open_at=None,
                total_rejections=0,
            )
        return self._circuits[card_id]

    def _should_transition_to_half_open(self, circuit: CircuitStatus) -> bool:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if circuit.state != CircuitState.OPEN:
            return False

        if not circuit.opened_at:
            return True

        opened_time = datetime.fromisoformat(circuit.opened_at)
        timeout = timedelta(seconds=self.config.reset_timeout_seconds)
        return _now_utc() >= opened_time + timeout

    def _log_event(self, event_type: str, card_id: str, data: Dict[str, Any]) -> None:
        """Log circuit event to ledger."""
        if self.ledger:
            self.ledger.log(
                event_type=f"circuit.{event_type}",
                card_id=card_id,
                actor="circuit_breaker",
                data=data,
            )

    def can_execute(self, card_id: str) -> bool:
        """
        Check if execution is allowed for a card.

        Args:
            card_id: Card identifier

        Returns:
            True if execution is allowed
        """
        circuit = self._get_or_create_circuit(card_id)

        if circuit.state == CircuitState.CLOSED:
            return True

        if circuit.state == CircuitState.OPEN:
            if self._should_transition_to_half_open(circuit):
                circuit.state = CircuitState.HALF_OPEN
                circuit.half_open_at = _now_utc().isoformat()
                circuit.success_count = 0
                self._save_state()
                self._log_event("half_open", card_id, {"from": "OPEN"})
                return True
            return False

        # HALF_OPEN - limited calls allowed
        return True

    def before_execute(self, card_id: str) -> None:
        """
        Call before executing an operation.

        Args:
            card_id: Card identifier

        Raises:
            CircuitOpenError: If circuit is open
        """
        circuit = self._get_or_create_circuit(card_id)

        if not self.can_execute(card_id):
            circuit.total_rejections += 1
            self._save_state()
            raise CircuitOpenError(card_id, circuit.failure_count)

    def record_success(self, card_id: str) -> None:
        """
        Record a successful execution.

        Args:
            card_id: Card identifier
        """
        circuit = self._get_or_create_circuit(card_id)
        now = _now_utc().isoformat()

        circuit.success_count += 1
        circuit.last_success_time = now

        if circuit.state == CircuitState.HALF_OPEN:
            if circuit.success_count >= self.config.success_threshold:
                # Close the circuit
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                circuit.opened_at = None
                circuit.half_open_at = None

                self._log_event("closed", card_id, {
                    "success_count": circuit.success_count,
                })

                if self.on_close:
                    self.on_close(card_id)

        self._save_state()

    def record_failure(self, card_id: str, error: Optional[str] = None) -> None:
        """
        Record a failed execution.

        Args:
            card_id: Card identifier
            error: Optional error message
        """
        circuit = self._get_or_create_circuit(card_id)
        now = _now_utc().isoformat()

        circuit.failure_count += 1
        circuit.last_failure_time = now
        circuit.success_count = 0  # Reset success count

        if circuit.state == CircuitState.HALF_OPEN:
            # Back to open
            circuit.state = CircuitState.OPEN
            circuit.opened_at = now
            circuit.half_open_at = None

            self._log_event("reopened", card_id, {
                "failure_count": circuit.failure_count,
                "error": error,
            })

        elif circuit.state == CircuitState.CLOSED:
            if circuit.failure_count >= self.config.failure_threshold:
                # Trip the circuit
                circuit.state = CircuitState.OPEN
                circuit.opened_at = now

                self._log_event("opened", card_id, {
                    "failure_count": circuit.failure_count,
                    "threshold": self.config.failure_threshold,
                    "error": error,
                })

                if self.on_open:
                    self.on_open(card_id, circuit.failure_count)

                # Check for escalation
                if self.on_escalate and circuit.failure_count >= self.config.failure_threshold * 2:
                    self.on_escalate(card_id, circuit.failure_count)

        self._save_state()

    def reset(self, card_id: str) -> None:
        """
        Manually reset a circuit to closed state.

        Args:
            card_id: Card identifier
        """
        circuit = self._get_or_create_circuit(card_id)
        old_state = circuit.state

        circuit.state = CircuitState.CLOSED
        circuit.failure_count = 0
        circuit.success_count = 0
        circuit.opened_at = None
        circuit.half_open_at = None

        self._save_state()

        self._log_event("reset", card_id, {
            "from_state": old_state.value,
        })

    def get_status(self, card_id: str) -> CircuitStatus:
        """Get current circuit status."""
        return self._get_or_create_circuit(card_id)

    def get_all_open(self) -> List[CircuitStatus]:
        """Get all cards with open circuits."""
        return [
            status for status in self._circuits.values()
            if status.state == CircuitState.OPEN
        ]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all circuits."""
        by_state = {state.value: 0 for state in CircuitState}
        total_rejections = 0

        for circuit in self._circuits.values():
            by_state[circuit.state.value] += 1
            total_rejections += circuit.total_rejections

        return {
            "total_circuits": len(self._circuits),
            "by_state": by_state,
            "total_rejections": total_rejections,
            "config": self.config.to_dict(),
        }
