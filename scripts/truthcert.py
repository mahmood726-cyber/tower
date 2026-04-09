#!/usr/bin/env python3
"""
TruthCert Integration for Tower
Evidence-grade validation with provenance, drift detection, and circuit breakers.

Inspired by TruthCert/Burhan spec - "every published number ships with its proof bundle"

Key concepts:
- P0/P1/P2 validator severity (Block/Warn/Info)
- Drift ledger (track unexpected changes)
- Circuit breaker (auto-block on system health degradation)
- Assurance ladder (Bronze/Silver/Gold badges)
- Witness chain (provenance for every artifact)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ============================================================
# Severity Classes (Validators as Law)
# ============================================================

class Severity(Enum):
    """Validator severity levels - validators are law."""
    P0_BLOCK = "P0"   # Must pass to publish (blocks merge)
    P1_WARN = "P1"    # Publish allowed but badge capped
    P2_INFO = "P2"    # Diagnostics only

    @property
    def blocks_publish(self) -> bool:
        return self == Severity.P0_BLOCK

    @property
    def caps_badge(self) -> bool:
        return self in (Severity.P0_BLOCK, Severity.P1_WARN)


class ValidationStatus(Enum):
    """Validation result status."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    NOT_RUN = "NOT_RUN"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    name: str
    severity: Severity
    status: ValidationStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    """Complete validation report for a card."""
    card_id: str
    timestamp: str
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def p0_passed(self) -> bool:
        """All P0 validators must pass."""
        p0_results = [r for r in self.results if r.severity == Severity.P0_BLOCK]
        return all(r.status == ValidationStatus.PASS for r in p0_results)

    @property
    def p1_passed(self) -> bool:
        """All P1 validators pass (no warnings)."""
        p1_results = [r for r in self.results if r.severity == Severity.P1_WARN]
        return all(r.status in (ValidationStatus.PASS, ValidationStatus.SKIP) for r in p1_results)

    @property
    def overall_status(self) -> str:
        if not self.p0_passed:
            return "BLOCKED"
        if not self.p1_passed:
            return "CAPPED"
        return "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "p0_passed": self.p0_passed,
            "p1_passed": self.p1_passed,
            "results": [r.to_dict() for r in self.results],
        }


# ============================================================
# Assurance Ladder (Bronze / Silver / Gold)
# ============================================================

class AssuranceLevel(Enum):
    """Assurance badge levels - algorithmic and versioned."""
    NONE = "none"           # No assurance (draft)
    BRONZE = "bronze"       # Map-grade: provenance + P0 pass + warnings allowed
    SILVER = "silver"       # Meta-grade: all P0 pass + P1 pass + conflicts resolved
    GOLD = "gold"           # Decision-grade: stable + reproducible + signed

    @property
    def ordinal(self) -> int:
        return {"none": 0, "bronze": 1, "silver": 2, "gold": 3}[self.value]


def compute_assurance_level(
    p0_passed: bool,
    p1_passed: bool,
    has_proofpack: bool,
    drift_clean: bool,
    conflicts_resolved: bool,
) -> AssuranceLevel:
    """
    Compute assurance level based on validation state.

    Bronze: P0 pass + provenance exists
    Silver: Bronze + P1 pass + conflicts resolved
    Gold: Silver + drift clean + proofpack exists
    """
    if not p0_passed:
        return AssuranceLevel.NONE

    # Bronze: P0 passed (warnings allowed)
    if not p1_passed or not conflicts_resolved:
        return AssuranceLevel.BRONZE

    # Silver: P0 + P1 pass + conflicts resolved
    if not drift_clean or not has_proofpack:
        return AssuranceLevel.SILVER

    # Gold: everything passes
    return AssuranceLevel.GOLD


# ============================================================
# Drift Ledger
# ============================================================

class DriftType(Enum):
    """Types of drift events."""
    SIGN_FLIP = "sign_flip"           # Result changed sign
    MAGNITUDE_CHANGE = "magnitude"     # Large change in value
    INCLUSION_CHANGE = "inclusion"     # Items added/removed
    STATUS_CHANGE = "status"           # Gate status changed
    SCHEMA_CHANGE = "schema"           # Schema version changed


@dataclass
class DriftEvent:
    """A detected drift event."""
    drift_type: DriftType
    card_id: str
    field: str
    old_value: Any
    new_value: Any
    timestamp: str
    severity: Severity = Severity.P1_WARN
    justification: Optional[str] = None
    adjudicated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_type": self.drift_type.value,
            "card_id": self.card_id,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "justification": self.justification,
            "adjudicated": self.adjudicated,
        }


class DriftLedger:
    """
    Tracks drift events across runs.
    Every release must emit drift events for significant changes.
    """

    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.events: List[DriftEvent] = []
        self._load()

    def _load(self) -> None:
        if self.ledger_path.exists():
            try:
                with open(self.ledger_path) as f:
                    data = json.load(f)
                for item in data.get("events", []):
                    self.events.append(DriftEvent(
                        drift_type=DriftType(item["drift_type"]),
                        card_id=item["card_id"],
                        field=item["field"],
                        old_value=item["old_value"],
                        new_value=item["new_value"],
                        timestamp=item["timestamp"],
                        severity=Severity(item.get("severity", "P1")),
                        justification=item.get("justification"),
                        adjudicated=item.get("adjudicated", False),
                    ))
            except (json.JSONDecodeError, KeyError):
                self.events = []

    def save(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "spec_version": "v1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "events": [e.to_dict() for e in self.events],
        }
        tmp_path = self.ledger_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(self.ledger_path)

    def add_event(self, event: DriftEvent) -> None:
        self.events.append(event)

    def detect_drift(
        self,
        card_id: str,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
    ) -> List[DriftEvent]:
        """Detect drift between old and new card state."""
        detected = []
        now = datetime.now(timezone.utc).isoformat()

        # Check gate status changes
        old_gates = old_state.get("gates", {})
        new_gates = new_state.get("gates", {})

        for gate in ["tests", "validators", "proofpack"]:
            old_val = old_gates.get(gate, "NOT_RUN")
            new_val = new_gates.get(gate, "NOT_RUN")

            if old_val != new_val:
                # Regression is P0, improvement is P2
                if old_val == "PASS" and new_val == "FAIL":
                    severity = Severity.P0_BLOCK
                elif old_val == "FAIL" and new_val == "PASS":
                    severity = Severity.P2_INFO
                else:
                    severity = Severity.P1_WARN

                event = DriftEvent(
                    drift_type=DriftType.STATUS_CHANGE,
                    card_id=card_id,
                    field=f"gates.{gate}",
                    old_value=old_val,
                    new_value=new_val,
                    timestamp=now,
                    severity=severity,
                )
                detected.append(event)

        # Check state changes
        old_card_state = old_state.get("state", "DRAFT")
        new_card_state = new_state.get("state", "DRAFT")

        if old_card_state != new_card_state:
            event = DriftEvent(
                drift_type=DriftType.STATUS_CHANGE,
                card_id=card_id,
                field="state",
                old_value=old_card_state,
                new_value=new_card_state,
                timestamp=now,
                severity=Severity.P2_INFO,
            )
            detected.append(event)

        # Check color/assurance changes
        old_color = old_state.get("color", "RED")
        new_color = new_state.get("color", "RED")

        if old_color != new_color:
            # Regression is higher severity
            color_order = {"GREEN": 2, "YELLOW": 1, "RED": 0}
            if color_order.get(new_color, 0) < color_order.get(old_color, 0):
                severity = Severity.P1_WARN
            else:
                severity = Severity.P2_INFO

            event = DriftEvent(
                drift_type=DriftType.STATUS_CHANGE,
                card_id=card_id,
                field="color",
                old_value=old_color,
                new_value=new_color,
                timestamp=now,
                severity=severity,
            )
            detected.append(event)

        return detected

    def unadjudicated_count(self, severity: Optional[Severity] = None) -> int:
        """Count unadjudicated drift events."""
        events = self.events
        if severity:
            events = [e for e in events if e.severity == severity]
        return sum(1 for e in events if not e.adjudicated)

    def recent_p0_failures(self, days: int = 7) -> int:
        """Count P0 drift events in recent days."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        for e in self.events:
            if e.severity == Severity.P0_BLOCK:
                try:
                    event_time = datetime.fromisoformat(e.timestamp.replace("Z", "+00:00"))
                    if event_time > cutoff:
                        count += 1
                except ValueError:
                    pass
        return count


# ============================================================
# Circuit Breaker
# ============================================================

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker thresholds."""
    max_p0_failures_per_week: int = 3
    max_unadjudicated_drift: int = 10
    max_consecutive_failures: int = 2


class CircuitBreaker:
    """
    Circuit breaker - stops the line when system health degrades.

    When tripped:
    - Only map-grade outputs allowed
    - Meta/transport/merge blocked
    - Drift ledger + diagnosis emitted
    """

    def __init__(
        self,
        config: CircuitBreakerConfig,
        drift_ledger: DriftLedger,
        status_path: Path,
    ):
        self.config = config
        self.drift_ledger = drift_ledger
        self.status_path = status_path
        self._consecutive_failures = 0

    def check_health(self) -> tuple[bool, List[str]]:
        """
        Check system health.
        Returns (healthy, reasons) tuple.
        """
        reasons = []

        # Check P0 failures in recent week
        p0_failures = self.drift_ledger.recent_p0_failures(days=7)
        if p0_failures >= self.config.max_p0_failures_per_week:
            reasons.append(f"P0 failures ({p0_failures}) >= threshold ({self.config.max_p0_failures_per_week})")

        # Check unadjudicated drift
        unadj = self.drift_ledger.unadjudicated_count()
        if unadj >= self.config.max_unadjudicated_drift:
            reasons.append(f"Unadjudicated drift ({unadj}) >= threshold ({self.config.max_unadjudicated_drift})")

        # Check consecutive failures
        if self._consecutive_failures >= self.config.max_consecutive_failures:
            reasons.append(f"Consecutive failures ({self._consecutive_failures}) >= threshold")

        return len(reasons) == 0, reasons

    def record_success(self) -> None:
        """Record a successful run."""
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed run."""
        self._consecutive_failures += 1

    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped."""
        healthy, _ = self.check_health()
        return not healthy

    def allow_merge(self) -> tuple[bool, str]:
        """Check if merges are allowed."""
        healthy, reasons = self.check_health()
        if not healthy:
            return False, f"Circuit breaker tripped: {'; '.join(reasons)}"
        return True, "OK"


# ============================================================
# Witness Chain (Provenance)
# ============================================================

@dataclass
class Witness:
    """A witness for a claim/artifact."""
    source_type: str  # "registry", "file", "run", "manual"
    locator: str      # Path, URL, or ID
    content_hash: Optional[str] = None
    timestamp: Optional[str] = None
    grade: str = "B"  # A (strong), B (medium), C (weak)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "locator": self.locator,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp,
            "grade": self.grade,
        }


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_witness_for_file(path: Path, grade: str = "A") -> Witness:
    """Create a witness for a file artifact."""
    return Witness(
        source_type="file",
        locator=str(path),
        content_hash=compute_file_hash(path) if path.exists() else None,
        timestamp=datetime.now(timezone.utc).isoformat(),
        grade=grade,
    )


def create_witness_for_run(run_id: str, git_sha: str, machine_id: str) -> Witness:
    """Create a witness for a capsule run."""
    return Witness(
        source_type="run",
        locator=f"run:{run_id}:{git_sha}:{machine_id}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        grade="A",
    )


# ============================================================
# Enhanced Proofpack Manifest (TruthCert Capsule)
# ============================================================

@dataclass
class CapsuleManifest:
    """
    TruthCert-style capsule manifest.
    Every published number ships with its proof bundle.
    """
    # Identity
    capsule_id: str = ""
    card_id: str = ""
    spec_version: str = "v1.5.7"

    # Timestamps
    created_at: str = ""

    # Code provenance
    git_sha: str = ""
    git_branch: str = ""
    code_hash: str = ""

    # Machine
    machine_id: str = ""

    # Inputs
    input_hashes: Dict[str, str] = field(default_factory=dict)

    # Witnesses
    witnesses: List[Dict[str, Any]] = field(default_factory=list)

    # Validation
    validation_report: Optional[Dict[str, Any]] = None
    assurance_level: str = "none"

    # Outputs
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    # Drift
    drift_events: List[Dict[str, Any]] = field(default_factory=list)

    def compute_capsule_id(self) -> str:
        """Compute capsule ID as SHA-256 of manifest content."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "card_id": self.card_id,
            "spec_version": self.spec_version,
            "created_at": self.created_at,
            "provenance": {
                "git_sha": self.git_sha,
                "git_branch": self.git_branch,
                "code_hash": self.code_hash,
                "machine_id": self.machine_id,
            },
            "input_hashes": self.input_hashes,
            "witnesses": self.witnesses,
            "validation": self.validation_report,
            "assurance_level": self.assurance_level,
            "artifacts": self.artifacts,
            "drift_events": self.drift_events,
        }


# ============================================================
# Seven Straight-Path Rules (Governance)
# ============================================================

STRAIGHT_PATH_RULES = """
Tower Governance Rules (inspired by TruthCert "Straight Path")

1) WITNESS-FIRST: No published artifact without a witness chain
   (immutable snapshot + locator + hash).

2) GUARDIANSHIP: Validators never generate; they only recompute/check/veto.
   Generator and validator code paths must be separate.

3) RIGHT NAMES: Card IDs, states, and gates follow strict schema.
   Free-form fields are allowed but don't affect gates.

4) MERCY-BY-IMPACT: Map-grade outputs publish early (Bronze).
   Meta/decision-grade require stronger gates (Silver/Gold).

5) CONSULTATION: Conflicts become explicit drift events.
   Adjudications are logged and replayable.

6) CHANGE-AWARE: Everything is versioned.
   Diffs + drift ledgers are mandatory.

7) ABSTENTION: "Insufficient certainty - do not publish" is first-class.
   Cards can be explicitly BLOCKED without shame.
"""


def print_governance_rules():
    """Print the governance rules."""
    print(STRAIGHT_PATH_RULES)


# ============================================================
# Main / CLI
# ============================================================

def main():
    """TruthCert CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TruthCert validation tools")
    parser.add_argument("command", choices=["rules", "drift", "health", "validate"])
    parser.add_argument("--card", help="Card ID")
    parser.add_argument("--tower-root", default=".", help="Tower root directory")

    args = parser.parse_args()
    tower_root = Path(args.tower_root)

    if args.command == "rules":
        print_governance_rules()

    elif args.command == "drift":
        ledger_path = tower_root / "control" / "drift_ledger.json"
        ledger = DriftLedger(ledger_path)
        print(f"Drift events: {len(ledger.events)}")
        print(f"Unadjudicated: {ledger.unadjudicated_count()}")
        print(f"P0 failures (7d): {ledger.recent_p0_failures()}")
        for event in ledger.events[-10:]:
            print(f"  [{event.severity.value}] {event.card_id}: {event.field} "
                  f"{event.old_value} -> {event.new_value}")

    elif args.command == "health":
        ledger_path = tower_root / "control" / "drift_ledger.json"
        status_path = tower_root / "control" / "status.json"
        ledger = DriftLedger(ledger_path)
        breaker = CircuitBreaker(CircuitBreakerConfig(), ledger, status_path)

        healthy, reasons = breaker.check_health()
        if healthy:
            print("System health: OK")
        else:
            print("System health: DEGRADED")
            for reason in reasons:
                print(f"  - {reason}")

        can_merge, msg = breaker.allow_merge()
        print(f"Merges allowed: {can_merge} ({msg})")

    elif args.command == "validate":
        if not args.card:
            print("ERROR: --card required for validate")
            sys.exit(1)
        print(f"Validating {args.card}...")
        # TODO: implement full validation
        print("(Validation not yet implemented)")


if __name__ == "__main__":
    main()
