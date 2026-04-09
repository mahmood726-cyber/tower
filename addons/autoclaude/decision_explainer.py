#!/usr/bin/env python3
"""
Decision Explainer - Transparent Decision Audit Trail

Inspired by:
- Quranic Hisab (Accountability): Every decision is explainable
- XAI (Explainable AI) principles

Features:
- Decision tree recording
- Reasoning chain capture
- Counterfactual explanations
- Audit trail generation
- Human-readable explanations
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import threading

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/decision_explainer.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DecisionType(Enum):
    """Types of decisions."""
    ROUTING = "routing"          # Which agent/tool to use
    SELECTION = "selection"      # Choosing among options
    VALIDATION = "validation"    # Accept/reject
    RETRY = "retry"              # Whether to retry
    ESCALATION = "escalation"    # Escalate to human
    TERMINATION = "termination"  # Stop processing
    TRANSFORMATION = "transformation"  # Data transformation choice


class ConfidenceLevel(Enum):
    """Confidence in decision."""
    VERY_HIGH = "very_high"    # > 0.9
    HIGH = "high"              # 0.7 - 0.9
    MEDIUM = "medium"          # 0.5 - 0.7
    LOW = "low"                # 0.3 - 0.5
    VERY_LOW = "very_low"      # < 0.3

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Get confidence level from numeric score."""
        if score > 0.9:
            return cls.VERY_HIGH
        elif score > 0.7:
            return cls.HIGH
        elif score > 0.5:
            return cls.MEDIUM
        elif score > 0.3:
            return cls.LOW
        else:
            return cls.VERY_LOW


@dataclass
class Factor:
    """A factor that influenced a decision."""
    name: str
    value: Any
    weight: float  # How much this factor influenced the decision (0.0 to 1.0)
    direction: str  # "positive", "negative", "neutral"
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "value": str(self.value) if not isinstance(self.value, (str, int, float, bool)) else self.value,
            "weight": self.weight,
            "direction": self.direction,
            "description": self.description
        }


@dataclass
class Alternative:
    """An alternative option that was considered."""
    name: str
    score: float
    rejected_reason: str
    factors: List[Factor] = field(default_factory=list)


@dataclass
class DecisionNode:
    """A node in the decision tree."""
    id: str
    decision_type: DecisionType
    question: str  # The question being answered
    context: Dict[str, Any]  # Input context
    options: List[str]  # Available options
    chosen: str  # The chosen option
    confidence: float  # 0.0 to 1.0
    factors: List[Factor]
    alternatives: List[Alternative]
    reasoning: str  # Natural language explanation
    timestamp: datetime = field(default_factory=_now_utc)
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "decision_type": self.decision_type.value,
            "question": self.question,
            "options": self.options,
            "chosen": self.chosen,
            "confidence": self.confidence,
            "confidence_level": ConfidenceLevel.from_score(self.confidence).value,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
            "factors": [f.to_dict() for f in self.factors],
            "alternatives": [
                {
                    "name": a.name,
                    "score": a.score,
                    "rejected_reason": a.rejected_reason
                }
                for a in self.alternatives
            ],
            "parent_id": self.parent_id,
            "children": self.children
        }


@dataclass
class ExplanationChain:
    """A chain of reasoning steps."""
    id: str
    task: str
    nodes: List[DecisionNode]
    final_outcome: str
    total_confidence: float
    started_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "task": self.task,
            "final_outcome": self.final_outcome,
            "total_confidence": self.total_confidence,
            "node_count": len(self.nodes),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "nodes": [n.to_dict() for n in self.nodes]
        }

    def to_natural_language(self) -> str:
        """Generate human-readable explanation."""
        lines = [f"Task: {self.task}", ""]
        lines.append("Decision Chain:")
        lines.append("-" * 40)

        for i, node in enumerate(self.nodes, 1):
            lines.append(f"\n{i}. {node.question}")
            lines.append(f"   Decision: {node.chosen}")
            lines.append(f"   Confidence: {node.confidence:.0%} ({ConfidenceLevel.from_score(node.confidence).value})")
            lines.append(f"   Reasoning: {node.reasoning}")

            if node.factors:
                lines.append("   Key factors:")
                for factor in sorted(node.factors, key=lambda f: f.weight, reverse=True)[:3]:
                    direction_symbol = "+" if factor.direction == "positive" else "-" if factor.direction == "negative" else "="
                    lines.append(f"      {direction_symbol} {factor.description} (weight: {factor.weight:.2f})")

            if node.alternatives:
                lines.append("   Alternatives considered:")
                for alt in node.alternatives[:2]:
                    lines.append(f"      - {alt.name}: rejected because {alt.rejected_reason}")

        lines.append("")
        lines.append("-" * 40)
        lines.append(f"Final Outcome: {self.final_outcome}")
        lines.append(f"Overall Confidence: {self.total_confidence:.0%}")

        return "\n".join(lines)


@dataclass
class CounterfactualExplanation:
    """What-if explanation for a decision."""
    original_decision: str
    changed_factor: str
    new_value: Any
    would_have_chosen: str
    confidence_change: float
    explanation: str


class DecisionExplainer:
    """
    Records and explains agent decisions.

    Hisab (Accountability) Principle: "Every soul will be held accountable" (74:38)
    - All decisions are recorded
    - Reasoning is transparent
    - Alternatives are documented
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        ledger_path: Optional[str] = None
    ):
        self._chains: Dict[str, ExplanationChain] = {}
        self._active_chain: Optional[ExplanationChain] = None
        self._all_nodes: Dict[str, DecisionNode] = {}
        self._storage_path = storage_path
        self._lock = threading.Lock()

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = _now_utc().isoformat()
        return f"{prefix}_{hashlib.sha256(timestamp.encode()).hexdigest()[:8]}"

    def start_chain(
        self,
        task: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExplanationChain:
        """Start a new explanation chain."""
        chain_id = self._generate_id("chain")
        chain = ExplanationChain(
            id=chain_id,
            task=task,
            nodes=[],
            final_outcome="",
            total_confidence=1.0,
            started_at=_now_utc(),
            metadata=metadata or {}
        )

        with self._lock:
            self._chains[chain_id] = chain
            self._active_chain = chain

        if self._logger:
            self._logger.log_event(
                event_type="EXPLANATION_CHAIN_START",
                card_id="autoclaude",
                details={"chain_id": chain_id, "task": task}
            )

        return chain

    def record_decision(
        self,
        decision_type: DecisionType,
        question: str,
        options: List[str],
        chosen: str,
        confidence: float,
        reasoning: str,
        factors: Optional[List[Factor]] = None,
        alternatives: Optional[List[Alternative]] = None,
        context: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        chain: Optional[ExplanationChain] = None
    ) -> DecisionNode:
        """Record a decision with full context."""
        node_id = self._generate_id("decision")

        node = DecisionNode(
            id=node_id,
            decision_type=decision_type,
            question=question,
            context=context or {},
            options=options,
            chosen=chosen,
            confidence=confidence,
            factors=factors or [],
            alternatives=alternatives or [],
            reasoning=reasoning,
            parent_id=parent_id
        )

        with self._lock:
            self._all_nodes[node_id] = node

            # Add to chain
            target_chain = chain or self._active_chain
            if target_chain:
                target_chain.nodes.append(node)
                # Update chain confidence (product of node confidences)
                target_chain.total_confidence *= confidence

            # Link to parent
            if parent_id and parent_id in self._all_nodes:
                self._all_nodes[parent_id].children.append(node_id)

        if self._logger:
            self._logger.log_event(
                event_type="DECISION_RECORDED",
                card_id="autoclaude",
                details={
                    "node_id": node_id,
                    "type": decision_type.value,
                    "question": question[:100],
                    "chosen": chosen,
                    "confidence": confidence
                }
            )

        return node

    def end_chain(
        self,
        outcome: str,
        chain: Optional[ExplanationChain] = None
    ) -> ExplanationChain:
        """Complete an explanation chain."""
        target_chain = chain or self._active_chain
        if not target_chain:
            raise ValueError("No active chain to end")

        with self._lock:
            target_chain.final_outcome = outcome
            target_chain.completed_at = _now_utc()

            if target_chain == self._active_chain:
                self._active_chain = None

        if self._logger:
            self._logger.log_event(
                event_type="EXPLANATION_CHAIN_END",
                card_id="autoclaude",
                details={
                    "chain_id": target_chain.id,
                    "outcome": outcome,
                    "node_count": len(target_chain.nodes),
                    "total_confidence": target_chain.total_confidence
                }
            )

        return target_chain

    def explain_decision(self, node_id: str) -> str:
        """Generate natural language explanation for a single decision."""
        node = self._all_nodes.get(node_id)
        if not node:
            return f"Decision {node_id} not found"

        lines = [
            f"Question: {node.question}",
            f"Decision: {node.chosen}",
            f"Confidence: {node.confidence:.0%} ({ConfidenceLevel.from_score(node.confidence).value})",
            "",
            f"Reasoning: {node.reasoning}",
            ""
        ]

        if node.factors:
            lines.append("Factors that influenced this decision:")
            for factor in sorted(node.factors, key=lambda f: f.weight, reverse=True):
                direction = {"positive": "+", "negative": "-", "neutral": "="}[factor.direction]
                lines.append(f"  {direction} {factor.description}")
                lines.append(f"    Weight: {factor.weight:.2f}, Value: {factor.value}")

        if node.alternatives:
            lines.append("")
            lines.append("Alternatives that were considered:")
            for alt in node.alternatives:
                lines.append(f"  - {alt.name} (score: {alt.score:.2f})")
                lines.append(f"    Rejected: {alt.rejected_reason}")

        return "\n".join(lines)

    def get_chain_explanation(self, chain_id: str) -> str:
        """Get full explanation for a chain."""
        chain = self._chains.get(chain_id)
        if not chain:
            return f"Chain {chain_id} not found"

        return chain.to_natural_language()

    def generate_counterfactual(
        self,
        node_id: str,
        change_factor: str,
        new_value: Any
    ) -> CounterfactualExplanation:
        """
        Generate a counterfactual explanation.

        "If factor X had been Y, what would have happened?"
        """
        node = self._all_nodes.get(node_id)
        if not node:
            raise ValueError(f"Decision {node_id} not found")

        # Find the factor
        original_factor = None
        for factor in node.factors:
            if factor.name == change_factor:
                original_factor = factor
                break

        if not original_factor:
            raise ValueError(f"Factor {change_factor} not found in decision")

        # Simulate what would have happened
        # This is a simplified simulation - in practice, you'd re-run the decision logic
        original_score = node.confidence
        weight = original_factor.weight

        # Estimate impact of change
        if original_factor.direction == "positive":
            # Positive factor becoming different might lower confidence
            new_confidence = original_score - (weight * 0.5)
        elif original_factor.direction == "negative":
            # Negative factor becoming different might raise confidence
            new_confidence = original_score + (weight * 0.5)
        else:
            new_confidence = original_score

        new_confidence = max(0.0, min(1.0, new_confidence))

        # Determine if different choice would be made
        if new_confidence < 0.5 and original_score >= 0.5:
            # Might have chosen differently
            if node.alternatives:
                would_have_chosen = node.alternatives[0].name
            else:
                would_have_chosen = f"possibly not {node.chosen}"
        else:
            would_have_chosen = node.chosen

        explanation = (
            f"If {change_factor} had been {new_value} instead of {original_factor.value}, "
            f"the confidence would have changed from {original_score:.0%} to {new_confidence:.0%}. "
        )

        if would_have_chosen != node.chosen:
            explanation += f"This might have led to choosing '{would_have_chosen}' instead of '{node.chosen}'."
        else:
            explanation += f"The decision would likely remain '{node.chosen}'."

        return CounterfactualExplanation(
            original_decision=node.chosen,
            changed_factor=change_factor,
            new_value=new_value,
            would_have_chosen=would_have_chosen,
            confidence_change=new_confidence - original_score,
            explanation=explanation
        )

    def get_decision_path(self, node_id: str) -> List[DecisionNode]:
        """Get the path of decisions leading to a node."""
        path = []
        current_id = node_id

        while current_id:
            node = self._all_nodes.get(current_id)
            if not node:
                break
            path.append(node)
            current_id = node.parent_id

        return list(reversed(path))

    def get_all_chains(
        self,
        completed_only: bool = False
    ) -> List[ExplanationChain]:
        """Get all explanation chains."""
        with self._lock:
            chains = list(self._chains.values())

        if completed_only:
            chains = [c for c in chains if c.completed_at is not None]

        return sorted(chains, key=lambda c: c.started_at, reverse=True)

    def export_chain(self, chain_id: str) -> Dict[str, Any]:
        """Export chain as structured data."""
        chain = self._chains.get(chain_id)
        if not chain:
            return {}
        return chain.to_dict()

    def generate_audit_report(
        self,
        chain_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate audit report for specified chains or all."""
        if chain_ids:
            chains = [self._chains[cid] for cid in chain_ids if cid in self._chains]
        else:
            chains = list(self._chains.values())

        total_decisions = sum(len(c.nodes) for c in chains)
        completed_chains = [c for c in chains if c.completed_at]

        # Aggregate confidence stats
        confidences = [n.confidence for c in chains for n in c.nodes]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Decision type distribution
        type_counts: Dict[str, int] = {}
        for chain in chains:
            for node in chain.nodes:
                t = node.decision_type.value
                type_counts[t] = type_counts.get(t, 0) + 1

        # Low confidence decisions
        low_confidence = [
            {"chain": c.id, "node": n.id, "question": n.question, "confidence": n.confidence}
            for c in chains for n in c.nodes
            if n.confidence < 0.5
        ]

        return {
            "generated_at": _now_utc().isoformat(),
            "total_chains": len(chains),
            "completed_chains": len(completed_chains),
            "total_decisions": total_decisions,
            "average_confidence": avg_confidence,
            "decision_type_distribution": type_counts,
            "low_confidence_decisions": low_confidence[:10],
            "chains_summary": [
                {
                    "id": c.id,
                    "task": c.task,
                    "outcome": c.final_outcome,
                    "confidence": c.total_confidence,
                    "decisions": len(c.nodes)
                }
                for c in chains
            ]
        }

    def save_to_storage(self) -> bool:
        """Persist all chains to storage."""
        if not self._storage_path:
            return False

        path = Path(self._storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "saved_at": _now_utc().isoformat(),
            "chains": [c.to_dict() for c in self._chains.values()]
        }

        path.write_text(json.dumps(data, indent=2))
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get explainer statistics."""
        with self._lock:
            return {
                "total_chains": len(self._chains),
                "total_decisions": len(self._all_nodes),
                "active_chain": self._active_chain.id if self._active_chain else None,
                "has_storage": self._storage_path is not None
            }


# Convenience exports
__all__ = [
    "DecisionExplainer",
    "DecisionNode",
    "ExplanationChain",
    "Factor",
    "Alternative",
    "CounterfactualExplanation",
    "DecisionType",
    "ConfidenceLevel"
]
