#!/usr/bin/env python3
"""
Human-in-the-Loop Checkpoints

Provides review gates for critical agent actions with:
- Configurable checkpoint triggers
- Approval workflows
- Timeout handling
- Audit trail for all decisions
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


class CheckpointStatus(Enum):
    """Status of a checkpoint request."""
    PENDING = "PENDING"          # Awaiting human decision
    APPROVED = "APPROVED"        # Human approved
    REJECTED = "REJECTED"        # Human rejected
    MODIFIED = "MODIFIED"        # Human approved with modifications
    TIMEOUT = "TIMEOUT"          # Timed out waiting for response
    AUTO_APPROVED = "AUTO_APPROVED"  # Auto-approved (low risk)
    ESCALATED = "ESCALATED"      # Escalated to higher authority


class CheckpointDecision(Enum):
    """Human decision at a checkpoint."""
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    ESCALATE = "escalate"


class RiskLevel(Enum):
    """Risk level for checkpoint triggers."""
    LOW = "low"           # Auto-approve allowed
    MEDIUM = "medium"     # Requires human review
    HIGH = "high"         # Requires human review + confirmation
    CRITICAL = "critical" # Requires multiple approvers


@dataclass
class CheckpointRequest:
    """A request for human review."""

    checkpoint_id: str
    card_id: str
    action_type: str              # Type of action (e.g., "code_change", "deploy")
    description: str              # Human-readable description
    risk_level: RiskLevel
    context: Dict[str, Any]       # Action context/details
    created_at: str
    created_by: str               # Agent/system that created checkpoint
    status: CheckpointStatus = CheckpointStatus.PENDING
    timeout_seconds: int = 3600   # 1 hour default
    expires_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    decision: Optional[CheckpointDecision] = None
    decision_reason: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.expires_at is None:
            expires = datetime.fromisoformat(self.created_at) + timedelta(seconds=self.timeout_seconds)
            self.expires_at = expires.isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        d["status"] = self.status.value
        d["decision"] = self.decision.value if self.decision else None
        return d

    def is_expired(self) -> bool:
        """Check if checkpoint has expired."""
        if self.status != CheckpointStatus.PENDING:
            return False
        if not self.expires_at:
            return False
        return _now_utc() > datetime.fromisoformat(self.expires_at)


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint behavior."""

    auto_approve_low_risk: bool = True
    default_timeout_seconds: int = 3600
    require_reason_on_reject: bool = True
    enable_escalation: bool = True
    escalation_timeout_seconds: int = 7200
    notify_channels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CheckpointTimeoutError(Exception):
    """Raised when checkpoint times out."""

    def __init__(self, checkpoint_id: str, timeout_seconds: int):
        self.checkpoint_id = checkpoint_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Checkpoint {checkpoint_id} timed out after {timeout_seconds}s")


class CheckpointRejectedError(Exception):
    """Raised when checkpoint is rejected."""

    def __init__(self, checkpoint_id: str, reason: Optional[str] = None):
        self.checkpoint_id = checkpoint_id
        self.reason = reason
        super().__init__(f"Checkpoint {checkpoint_id} rejected: {reason or 'No reason provided'}")


class HumanCheckpoint:
    """
    Human-in-the-loop checkpoint system.

    Features:
    - Risk-based checkpoint triggers
    - Approval/rejection workflows
    - Timeout handling with configurable behavior
    - Modification support
    - Escalation paths
    - Full audit trail
    """

    def __init__(
        self,
        config: Optional[CheckpointConfig] = None,
        checkpoint_path: Optional[str] = None,
        on_checkpoint_created: Optional[Callable[[CheckpointRequest], None]] = None,
        on_checkpoint_resolved: Optional[Callable[[CheckpointRequest], None]] = None,
        on_timeout: Optional[Callable[[CheckpointRequest], None]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize checkpoint system.

        Args:
            config: Checkpoint configuration
            checkpoint_path: Path to persist checkpoints
            on_checkpoint_created: Callback when checkpoint created
            on_checkpoint_resolved: Callback when checkpoint resolved
            on_timeout: Callback when checkpoint times out
            ledger: Optional EventLogger for audit trail
        """
        self.config = config or CheckpointConfig()

        if checkpoint_path:
            self.checkpoint_path = Path(checkpoint_path)
        else:
            self.checkpoint_path = CONTROL_DIR / "checkpoints.json"

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self.on_checkpoint_created = on_checkpoint_created
        self.on_checkpoint_resolved = on_checkpoint_resolved
        self.on_timeout = on_timeout
        self.ledger = ledger

        self._checkpoints: Dict[str, CheckpointRequest] = {}
        self._load()

    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID."""
        ts = _now_utc().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        return f"ckpt_{ts}_{suffix}"

    def _load(self) -> None:
        """Load persisted checkpoints."""
        if not self.checkpoint_path.exists():
            return

        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for ckpt_data in data.get("checkpoints", []):
                ckpt_data["risk_level"] = RiskLevel(ckpt_data["risk_level"])
                ckpt_data["status"] = CheckpointStatus(ckpt_data["status"])
                if ckpt_data.get("decision"):
                    ckpt_data["decision"] = CheckpointDecision(ckpt_data["decision"])
                else:
                    ckpt_data["decision"] = None

                checkpoint = CheckpointRequest(**ckpt_data)
                self._checkpoints[checkpoint.checkpoint_id] = checkpoint

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self._checkpoints = {}

    def _save(self) -> None:
        """Persist checkpoints."""
        data = {
            "last_updated": _now_utc().isoformat(),
            "config": self.config.to_dict(),
            "checkpoints": [c.to_dict() for c in self._checkpoints.values()],
        }

        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.checkpoint_path)

    def _log_event(
        self,
        event_type: str,
        checkpoint_id: str,
        card_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Log checkpoint event to ledger."""
        if self.ledger:
            self.ledger.log(
                event_type=f"checkpoint.{event_type}",
                card_id=card_id,
                actor="human_checkpoint",
                data={"checkpoint_id": checkpoint_id, **data},
            )

    def create(
        self,
        card_id: str,
        action_type: str,
        description: str,
        risk_level: RiskLevel,
        context: Optional[Dict[str, Any]] = None,
        created_by: str = "agent",
        timeout_seconds: Optional[int] = None,
    ) -> CheckpointRequest:
        """
        Create a checkpoint for human review.

        Args:
            card_id: Associated card ID
            action_type: Type of action requiring review
            description: Human-readable description
            risk_level: Risk level of the action
            context: Additional context/details
            created_by: Identifier of creator
            timeout_seconds: Override default timeout

        Returns:
            CheckpointRequest
        """
        checkpoint_id = self._generate_checkpoint_id()
        now = _now_utc().isoformat()
        timeout = timeout_seconds or self.config.default_timeout_seconds

        checkpoint = CheckpointRequest(
            checkpoint_id=checkpoint_id,
            card_id=card_id,
            action_type=action_type,
            description=description,
            risk_level=risk_level,
            context=context or {},
            created_at=now,
            created_by=created_by,
            timeout_seconds=timeout,
        )

        # Auto-approve low risk if configured
        if risk_level == RiskLevel.LOW and self.config.auto_approve_low_risk:
            checkpoint.status = CheckpointStatus.AUTO_APPROVED
            checkpoint.reviewed_at = now
            checkpoint.reviewed_by = "system"
            checkpoint.decision = CheckpointDecision.APPROVE

            self._log_event("auto_approved", checkpoint_id, card_id, {
                "action_type": action_type,
                "risk_level": risk_level.value,
            })
        else:
            self._log_event("created", checkpoint_id, card_id, {
                "action_type": action_type,
                "risk_level": risk_level.value,
                "description": description,
                "expires_at": checkpoint.expires_at,
            })

            if self.on_checkpoint_created:
                self.on_checkpoint_created(checkpoint)

        self._checkpoints[checkpoint_id] = checkpoint
        self._save()

        return checkpoint

    def resolve(
        self,
        checkpoint_id: str,
        decision: CheckpointDecision,
        reviewed_by: str,
        reason: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> CheckpointRequest:
        """
        Resolve a checkpoint with a human decision.

        Args:
            checkpoint_id: Checkpoint ID
            decision: Human decision
            reviewed_by: Identifier of reviewer
            reason: Optional reason for decision
            modifications: Optional modifications (for MODIFY decision)

        Returns:
            Updated CheckpointRequest

        Raises:
            KeyError: If checkpoint not found
            ValueError: If checkpoint already resolved or expired
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        if checkpoint.status != CheckpointStatus.PENDING:
            raise ValueError(f"Checkpoint already resolved: {checkpoint.status.value}")

        # Check for timeout
        if checkpoint.is_expired():
            checkpoint.status = CheckpointStatus.TIMEOUT
            self._save()
            raise ValueError(f"Checkpoint has expired")

        # Validate rejection reason if required
        if (
            decision == CheckpointDecision.REJECT
            and self.config.require_reason_on_reject
            and not reason
        ):
            raise ValueError("Reason required for rejection")

        # Update checkpoint
        now = _now_utc().isoformat()
        checkpoint.reviewed_at = now
        checkpoint.reviewed_by = reviewed_by
        checkpoint.decision = decision
        checkpoint.decision_reason = reason

        if decision == CheckpointDecision.APPROVE:
            checkpoint.status = CheckpointStatus.APPROVED
        elif decision == CheckpointDecision.REJECT:
            checkpoint.status = CheckpointStatus.REJECTED
        elif decision == CheckpointDecision.MODIFY:
            checkpoint.status = CheckpointStatus.MODIFIED
            checkpoint.modifications = modifications
        elif decision == CheckpointDecision.ESCALATE:
            checkpoint.status = CheckpointStatus.ESCALATED
            # Extend timeout for escalation
            checkpoint.timeout_seconds = self.config.escalation_timeout_seconds
            expires = datetime.fromisoformat(now) + timedelta(
                seconds=self.config.escalation_timeout_seconds
            )
            checkpoint.expires_at = expires.isoformat()

        self._save()

        self._log_event("resolved", checkpoint_id, checkpoint.card_id, {
            "decision": decision.value,
            "reviewed_by": reviewed_by,
            "reason": reason,
        })

        if self.on_checkpoint_resolved:
            self.on_checkpoint_resolved(checkpoint)

        return checkpoint

    def wait_for_resolution(
        self,
        checkpoint_id: str,
        poll_interval: float = 5.0,
        timeout_override: Optional[int] = None,
    ) -> CheckpointRequest:
        """
        Block until checkpoint is resolved.

        Args:
            checkpoint_id: Checkpoint ID
            poll_interval: Seconds between status checks
            timeout_override: Override checkpoint timeout

        Returns:
            Resolved CheckpointRequest

        Raises:
            KeyError: If checkpoint not found
            CheckpointTimeoutError: If checkpoint times out
            CheckpointRejectedError: If checkpoint rejected
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        timeout = timeout_override or checkpoint.timeout_seconds
        start_time = time.monotonic()

        while True:
            # Reload from disk (in case external process updated)
            self._load()
            checkpoint = self._checkpoints.get(checkpoint_id)

            if not checkpoint:
                raise KeyError(f"Checkpoint not found: {checkpoint_id}")

            # Check if resolved
            if checkpoint.status != CheckpointStatus.PENDING:
                if checkpoint.status == CheckpointStatus.REJECTED:
                    raise CheckpointRejectedError(
                        checkpoint_id,
                        checkpoint.decision_reason,
                    )
                return checkpoint

            # Check timeout
            elapsed = time.monotonic() - start_time
            if elapsed > timeout:
                checkpoint.status = CheckpointStatus.TIMEOUT
                self._save()

                self._log_event("timeout", checkpoint_id, checkpoint.card_id, {
                    "timeout_seconds": timeout,
                })

                if self.on_timeout:
                    self.on_timeout(checkpoint)

                raise CheckpointTimeoutError(checkpoint_id, timeout)

            time.sleep(poll_interval)

    def get(self, checkpoint_id: str) -> Optional[CheckpointRequest]:
        """Get checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    def get_pending(self, card_id: Optional[str] = None) -> List[CheckpointRequest]:
        """
        Get all pending checkpoints.

        Args:
            card_id: Optional filter by card ID

        Returns:
            List of pending checkpoints
        """
        # Check for expirations
        for checkpoint in self._checkpoints.values():
            if checkpoint.status == CheckpointStatus.PENDING and checkpoint.is_expired():
                checkpoint.status = CheckpointStatus.TIMEOUT
                self._log_event("timeout", checkpoint.checkpoint_id, checkpoint.card_id, {})

        self._save()

        result = []
        for checkpoint in self._checkpoints.values():
            if checkpoint.status == CheckpointStatus.PENDING:
                if card_id is None or checkpoint.card_id == card_id:
                    result.append(checkpoint)

        return sorted(result, key=lambda c: c.created_at)

    def get_by_card(self, card_id: str) -> List[CheckpointRequest]:
        """Get all checkpoints for a card."""
        return [
            c for c in self._checkpoints.values()
            if c.card_id == card_id
        ]

    def cancel(self, checkpoint_id: str, reason: str = "cancelled") -> None:
        """
        Cancel a pending checkpoint.

        Args:
            checkpoint_id: Checkpoint ID
            reason: Cancellation reason
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        if checkpoint.status != CheckpointStatus.PENDING:
            raise ValueError(f"Cannot cancel: checkpoint is {checkpoint.status.value}")

        checkpoint.status = CheckpointStatus.REJECTED
        checkpoint.decision = CheckpointDecision.REJECT
        checkpoint.decision_reason = reason
        checkpoint.reviewed_at = _now_utc().isoformat()
        checkpoint.reviewed_by = "system"

        self._save()

        self._log_event("cancelled", checkpoint_id, checkpoint.card_id, {
            "reason": reason,
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all checkpoints."""
        by_status = {status.value: 0 for status in CheckpointStatus}
        by_risk = {risk.value: 0 for risk in RiskLevel}
        pending_count = 0

        for checkpoint in self._checkpoints.values():
            by_status[checkpoint.status.value] += 1
            by_risk[checkpoint.risk_level.value] += 1
            if checkpoint.status == CheckpointStatus.PENDING:
                pending_count += 1

        return {
            "total_checkpoints": len(self._checkpoints),
            "pending": pending_count,
            "by_status": by_status,
            "by_risk": by_risk,
            "config": self.config.to_dict(),
        }
