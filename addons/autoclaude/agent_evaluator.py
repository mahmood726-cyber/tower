#!/usr/bin/env python3
"""
Agent Evaluator - Offline/Online Evaluation & LLM-as-Judge

Inspired by:
- LangChain State of Agent Engineering: "LLM-as-judge (53.3%) for breadth, human review (59.8%) for depth"
- Quranic Hisab (Accountability): Every action is accountable

Features:
- Offline evaluation with test cases
- Online evaluation of production traces
- LLM-as-judge scoring
- Human review queue
- Quality metrics and trending
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import threading
import statistics

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/agent_evaluator.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class EvalType(Enum):
    """Types of evaluations."""
    OFFLINE = "offline"      # Pre-defined test cases
    ONLINE = "online"        # Production traces
    HUMAN = "human"          # Human review
    LLM_JUDGE = "llm_judge"  # LLM-as-judge


class ScoreType(Enum):
    """Types of scoring metrics."""
    BINARY = "binary"        # Pass/fail
    NUMERIC = "numeric"      # 0.0 to 1.0
    CATEGORICAL = "categorical"  # Labels
    RUBRIC = "rubric"        # Multi-criteria


class ReviewStatus(Enum):
    """Status of human review items."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


@dataclass
class EvalCriteria:
    """Evaluation criteria definition."""
    name: str
    description: str
    score_type: ScoreType
    weight: float = 1.0
    passing_threshold: float = 0.7
    categories: Optional[List[str]] = None  # For categorical scoring
    rubric: Optional[Dict[str, str]] = None  # For rubric scoring


@dataclass
class TestCase:
    """A single test case for offline evaluation."""
    id: str
    name: str
    description: str
    input_data: Any
    expected_output: Any
    criteria: List[str]  # Names of EvalCriteria to use
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalScore:
    """Score from an evaluation."""
    criteria_name: str
    score: Union[bool, float, str]
    score_type: ScoreType
    passed: bool
    reasoning: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Complete result of an evaluation."""
    id: str
    test_case_id: Optional[str]
    eval_type: EvalType
    input_data: Any
    actual_output: Any
    expected_output: Optional[Any]
    scores: List[EvalScore]
    passed: bool
    overall_score: float
    duration_ms: float
    evaluated_at: datetime = field(default_factory=_now_utc)
    evaluator: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "eval_type": self.eval_type.value,
            "passed": self.passed,
            "overall_score": self.overall_score,
            "duration_ms": self.duration_ms,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluator": self.evaluator,
            "scores": [
                {
                    "criteria": s.criteria_name,
                    "score": s.score,
                    "passed": s.passed,
                    "reasoning": s.reasoning
                }
                for s in self.scores
            ]
        }


@dataclass
class ReviewItem:
    """Item pending human review."""
    id: str
    content: Any
    context: Dict[str, Any]
    status: ReviewStatus
    priority: int = 5
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=_now_utc)
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    decision: Optional[str] = None


@dataclass
class QualityMetrics:
    """Aggregated quality metrics."""
    period: str  # "hour", "day", "week"
    total_evaluations: int
    pass_rate: float
    average_score: float
    score_std_dev: float
    by_criteria: Dict[str, Dict[str, float]]
    by_eval_type: Dict[str, int]
    trend: str  # "improving", "stable", "declining"


@dataclass
class EvalReport:
    """Complete evaluation report."""
    generated_at: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    average_score: float
    results: List[EvalResult]
    metrics_by_criteria: Dict[str, Dict[str, float]]
    failures: List[Dict[str, Any]]


class AgentEvaluator:
    """
    Comprehensive agent evaluation system.

    Hisab (Accountability) Principle: "Every soul will be held accountable" (74:38)
    - Complete audit trail of all evaluations
    - Transparent scoring with reasoning
    - Fair and consistent judgment
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        ledger_path: Optional[str] = None
    ):
        self._criteria: Dict[str, EvalCriteria] = {}
        self._test_cases: Dict[str, TestCase] = {}
        self._results: List[EvalResult] = []
        self._review_queue: Dict[str, ReviewItem] = {}
        self._custom_scorers: Dict[str, Callable] = {}
        self._llm_judge_fn: Optional[Callable] = None
        self._storage_path = storage_path
        self._lock = threading.Lock()

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

        # Register default criteria
        self._register_default_criteria()

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        timestamp = _now_utc().isoformat()
        return f"{prefix}_{hashlib.sha256(timestamp.encode()).hexdigest()[:8]}"

    def _register_default_criteria(self) -> None:
        """Register common evaluation criteria."""
        default_criteria = [
            EvalCriteria(
                name="correctness",
                description="Output matches expected result",
                score_type=ScoreType.BINARY,
                passing_threshold=1.0
            ),
            EvalCriteria(
                name="relevance",
                description="Output is relevant to the input",
                score_type=ScoreType.NUMERIC,
                passing_threshold=0.7
            ),
            EvalCriteria(
                name="completeness",
                description="Output covers all required aspects",
                score_type=ScoreType.NUMERIC,
                passing_threshold=0.8
            ),
            EvalCriteria(
                name="safety",
                description="Output contains no harmful content",
                score_type=ScoreType.BINARY,
                passing_threshold=1.0,
                weight=2.0
            ),
            EvalCriteria(
                name="coherence",
                description="Output is logically coherent",
                score_type=ScoreType.NUMERIC,
                passing_threshold=0.7
            ),
            EvalCriteria(
                name="factuality",
                description="Output is factually accurate",
                score_type=ScoreType.NUMERIC,
                passing_threshold=0.8
            )
        ]

        for criteria in default_criteria:
            self._criteria[criteria.name] = criteria

    def register_criteria(self, criteria: EvalCriteria) -> None:
        """Register custom evaluation criteria."""
        self._criteria[criteria.name] = criteria

    def register_custom_scorer(
        self,
        criteria_name: str,
        scorer: Callable[[Any, Any, Optional[Any]], EvalScore]
    ) -> None:
        """Register custom scoring function for a criteria."""
        self._custom_scorers[criteria_name] = scorer

    def set_llm_judge(
        self,
        judge_fn: Callable[[str, Any, Any, EvalCriteria], EvalScore]
    ) -> None:
        """Set the LLM-as-judge function."""
        self._llm_judge_fn = judge_fn

    def add_test_case(
        self,
        name: str,
        description: str,
        input_data: Any,
        expected_output: Any,
        criteria: List[str],
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TestCase:
        """Add a test case for offline evaluation."""
        case_id = self._generate_id("case")
        test_case = TestCase(
            id=case_id,
            name=name,
            description=description,
            input_data=input_data,
            expected_output=expected_output,
            criteria=criteria,
            tags=tags or [],
            metadata=metadata or {}
        )

        with self._lock:
            self._test_cases[case_id] = test_case

        return test_case

    def run_offline_eval(
        self,
        agent_fn: Callable[[Any], Any],
        test_case_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> EvalReport:
        """
        Run offline evaluation against test cases.

        Args:
            agent_fn: Function that takes input and returns output
            test_case_ids: Specific cases to run (all if None)
            tags: Filter cases by tags
        """
        # Select test cases
        cases = list(self._test_cases.values())

        if test_case_ids:
            cases = [c for c in cases if c.id in test_case_ids]

        if tags:
            tag_set = set(tags)
            cases = [c for c in cases if tag_set & set(c.tags)]

        results: List[EvalResult] = []
        passed = 0
        failed = 0

        for case in cases:
            start_time = _now_utc()

            try:
                actual_output = agent_fn(case.input_data)
                duration_ms = (_now_utc() - start_time).total_seconds() * 1000

                # Score against criteria
                scores = self._evaluate_output(
                    actual_output,
                    case.expected_output,
                    case.criteria
                )

                # Calculate overall score
                overall_score = self._calculate_overall_score(scores)
                case_passed = all(s.passed for s in scores)

                result = EvalResult(
                    id=self._generate_id("result"),
                    test_case_id=case.id,
                    eval_type=EvalType.OFFLINE,
                    input_data=case.input_data,
                    actual_output=actual_output,
                    expected_output=case.expected_output,
                    scores=scores,
                    passed=case_passed,
                    overall_score=overall_score,
                    duration_ms=duration_ms
                )

                if case_passed:
                    passed += 1
                else:
                    failed += 1

            except Exception as e:
                duration_ms = (_now_utc() - start_time).total_seconds() * 1000
                result = EvalResult(
                    id=self._generate_id("result"),
                    test_case_id=case.id,
                    eval_type=EvalType.OFFLINE,
                    input_data=case.input_data,
                    actual_output=None,
                    expected_output=case.expected_output,
                    scores=[],
                    passed=False,
                    overall_score=0.0,
                    duration_ms=duration_ms,
                    metadata={"error": str(e)}
                )
                failed += 1

            results.append(result)
            with self._lock:
                self._results.append(result)

        # Generate report
        total = len(results)
        pass_rate = passed / total if total > 0 else 0.0
        avg_score = statistics.mean(r.overall_score for r in results) if results else 0.0

        # Aggregate by criteria
        metrics_by_criteria: Dict[str, Dict[str, float]] = {}
        for result in results:
            for score in result.scores:
                if score.criteria_name not in metrics_by_criteria:
                    metrics_by_criteria[score.criteria_name] = {"scores": [], "passed": 0, "total": 0}
                if isinstance(score.score, (int, float)):
                    metrics_by_criteria[score.criteria_name]["scores"].append(float(score.score))
                if score.passed:
                    metrics_by_criteria[score.criteria_name]["passed"] += 1
                metrics_by_criteria[score.criteria_name]["total"] += 1

        for name, data in metrics_by_criteria.items():
            scores_list = data.get("scores", [])
            data["average"] = statistics.mean(scores_list) if scores_list else 0.0
            data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0.0
            del data["scores"]

        failures = [
            {"case_id": r.test_case_id, "error": r.metadata.get("error", "Failed criteria")}
            for r in results if not r.passed
        ]

        report = EvalReport(
            generated_at=_now_utc(),
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            pass_rate=pass_rate,
            average_score=avg_score,
            results=results,
            metrics_by_criteria=metrics_by_criteria,
            failures=failures
        )

        if self._logger:
            self._logger.log_event(
                event_type="EVAL_COMPLETE",
                card_id="autoclaude",
                details={
                    "eval_type": "offline",
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": pass_rate
                }
            )

        return report

    def _evaluate_output(
        self,
        actual: Any,
        expected: Optional[Any],
        criteria_names: List[str]
    ) -> List[EvalScore]:
        """Evaluate output against specified criteria."""
        scores: List[EvalScore] = []

        for name in criteria_names:
            criteria = self._criteria.get(name)
            if not criteria:
                continue

            # Use custom scorer if available
            if name in self._custom_scorers:
                score = self._custom_scorers[name](actual, expected, criteria)
            else:
                score = self._default_score(actual, expected, criteria)

            scores.append(score)

        return scores

    def _default_score(
        self,
        actual: Any,
        expected: Optional[Any],
        criteria: EvalCriteria
    ) -> EvalScore:
        """Default scoring logic."""
        if criteria.score_type == ScoreType.BINARY:
            # Exact match for binary
            if criteria.name == "correctness":
                passed = self._compare_outputs(actual, expected)
                return EvalScore(
                    criteria_name=criteria.name,
                    score=passed,
                    score_type=ScoreType.BINARY,
                    passed=passed,
                    reasoning="Exact match comparison"
                )
            else:
                # Default binary pass
                return EvalScore(
                    criteria_name=criteria.name,
                    score=True,
                    score_type=ScoreType.BINARY,
                    passed=True,
                    reasoning="Default pass"
                )

        elif criteria.score_type == ScoreType.NUMERIC:
            # Calculate similarity score
            if expected is not None:
                score = self._calculate_similarity(actual, expected)
            else:
                score = 0.5  # Neutral when no expected

            passed = score >= criteria.passing_threshold
            return EvalScore(
                criteria_name=criteria.name,
                score=score,
                score_type=ScoreType.NUMERIC,
                passed=passed,
                reasoning=f"Similarity: {score:.2f}, threshold: {criteria.passing_threshold}"
            )

        else:
            # Default neutral score
            return EvalScore(
                criteria_name=criteria.name,
                score=0.5,
                score_type=ScoreType.NUMERIC,
                passed=True,
                reasoning="Default score"
            )

    def _compare_outputs(self, actual: Any, expected: Any) -> bool:
        """Compare two outputs for equality."""
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False

        # String comparison
        if isinstance(expected, str) and isinstance(actual, str):
            return actual.strip().lower() == expected.strip().lower()

        # Dict comparison
        if isinstance(expected, dict) and isinstance(actual, dict):
            return json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)

        # List comparison
        if isinstance(expected, list) and isinstance(actual, list):
            return actual == expected

        # General equality
        return actual == expected

    def _calculate_similarity(self, actual: Any, expected: Any) -> float:
        """Calculate similarity between outputs."""
        if actual is None:
            return 0.0
        if expected is None:
            return 0.5

        # String similarity (Jaccard)
        if isinstance(expected, str) and isinstance(actual, str):
            words1 = set(actual.lower().split())
            words2 = set(expected.lower().split())
            if not words1 and not words2:
                return 1.0
            if not words1 or not words2:
                return 0.0
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union

        # Dict key overlap
        if isinstance(expected, dict) and isinstance(actual, dict):
            keys1 = set(actual.keys())
            keys2 = set(expected.keys())
            if not keys2:
                return 1.0
            return len(keys1 & keys2) / len(keys2)

        # List overlap
        if isinstance(expected, list) and isinstance(actual, list):
            if not expected:
                return 1.0
            overlap = len(set(map(str, actual)) & set(map(str, expected)))
            return overlap / len(expected)

        # Fallback
        return 1.0 if actual == expected else 0.0

    def _calculate_overall_score(self, scores: List[EvalScore]) -> float:
        """Calculate weighted overall score."""
        if not scores:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for score in scores:
            criteria = self._criteria.get(score.criteria_name)
            weight = criteria.weight if criteria else 1.0

            if score.score_type == ScoreType.BINARY:
                value = 1.0 if score.score else 0.0
            elif score.score_type == ScoreType.NUMERIC:
                value = float(score.score) if isinstance(score.score, (int, float)) else 0.5
            else:
                value = 1.0 if score.passed else 0.0

            weighted_sum += value * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def run_online_eval(
        self,
        traces: List[Dict[str, Any]],
        criteria: List[str]
    ) -> QualityMetrics:
        """
        Evaluate production traces for quality monitoring.

        Args:
            traces: List of production trace records
            criteria: Criteria to evaluate against
        """
        if not traces:
            return QualityMetrics(
                period="current",
                total_evaluations=0,
                pass_rate=0.0,
                average_score=0.0,
                score_std_dev=0.0,
                by_criteria={},
                by_eval_type={EvalType.ONLINE.value: 0},
                trend="stable"
            )

        all_scores: List[float] = []
        by_criteria: Dict[str, List[float]] = {c: [] for c in criteria}
        passed_count = 0

        for trace in traces:
            input_data = trace.get("input")
            output_data = trace.get("output")

            scores = self._evaluate_output(output_data, None, criteria)

            for score in scores:
                if score.criteria_name in by_criteria:
                    if isinstance(score.score, (int, float)):
                        by_criteria[score.criteria_name].append(float(score.score))

            overall = self._calculate_overall_score(scores)
            all_scores.append(overall)

            if all(s.passed for s in scores):
                passed_count += 1

            # Log result
            result = EvalResult(
                id=self._generate_id("online"),
                test_case_id=None,
                eval_type=EvalType.ONLINE,
                input_data=input_data,
                actual_output=output_data,
                expected_output=None,
                scores=scores,
                passed=all(s.passed for s in scores),
                overall_score=overall,
                duration_ms=0.0
            )
            with self._lock:
                self._results.append(result)

        # Calculate metrics
        avg_score = statistics.mean(all_scores) if all_scores else 0.0
        std_dev = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
        pass_rate = passed_count / len(traces) if traces else 0.0

        criteria_metrics = {}
        for name, scores_list in by_criteria.items():
            if scores_list:
                criteria_metrics[name] = {
                    "average": statistics.mean(scores_list),
                    "min": min(scores_list),
                    "max": max(scores_list)
                }

        # Determine trend (compare with historical)
        trend = self._calculate_trend(all_scores)

        return QualityMetrics(
            period="current",
            total_evaluations=len(traces),
            pass_rate=pass_rate,
            average_score=avg_score,
            score_std_dev=std_dev,
            by_criteria=criteria_metrics,
            by_eval_type={EvalType.ONLINE.value: len(traces)},
            trend=trend
        )

    def _calculate_trend(self, recent_scores: List[float]) -> str:
        """Calculate trend based on recent scores."""
        if len(recent_scores) < 5:
            return "stable"

        # Compare first half vs second half
        mid = len(recent_scores) // 2
        first_half = statistics.mean(recent_scores[:mid])
        second_half = statistics.mean(recent_scores[mid:])

        diff = second_half - first_half
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        return "stable"

    def llm_as_judge(
        self,
        prompt: str,
        output: Any,
        criteria: EvalCriteria
    ) -> EvalScore:
        """
        Use LLM as judge for evaluation.

        Requires set_llm_judge() to be called first.
        """
        if not self._llm_judge_fn:
            raise ValueError("LLM judge function not set. Call set_llm_judge() first.")

        return self._llm_judge_fn(prompt, output, None, criteria)

    def add_to_review_queue(
        self,
        content: Any,
        context: Dict[str, Any],
        priority: int = 5
    ) -> ReviewItem:
        """Add item to human review queue."""
        item_id = self._generate_id("review")
        item = ReviewItem(
            id=item_id,
            content=content,
            context=context,
            status=ReviewStatus.PENDING,
            priority=priority
        )

        with self._lock:
            self._review_queue[item_id] = item

        if self._logger:
            self._logger.log_event(
                event_type="REVIEW_QUEUED",
                card_id="autoclaude",
                details={"item_id": item_id, "priority": priority}
            )

        return item

    def get_review_queue(
        self,
        status: Optional[ReviewStatus] = None,
        limit: int = 20
    ) -> List[ReviewItem]:
        """Get items from review queue."""
        with self._lock:
            items = list(self._review_queue.values())

        if status:
            items = [i for i in items if i.status == status]

        # Sort by priority (higher first), then by created_at
        items.sort(key=lambda x: (-x.priority, x.created_at))

        return items[:limit]

    def submit_review(
        self,
        item_id: str,
        decision: str,
        notes: Optional[str] = None,
        reviewer: str = "human"
    ) -> bool:
        """Submit human review decision."""
        with self._lock:
            item = self._review_queue.get(item_id)
            if not item:
                return False

            if decision == "approve":
                item.status = ReviewStatus.APPROVED
            elif decision == "reject":
                item.status = ReviewStatus.REJECTED
            else:
                item.status = ReviewStatus.NEEDS_REVISION

            item.decision = decision
            item.reviewer_notes = notes
            item.reviewed_at = _now_utc()

        if self._logger:
            self._logger.log_event(
                event_type="REVIEW_SUBMITTED",
                card_id="autoclaude",
                details={
                    "item_id": item_id,
                    "decision": decision,
                    "reviewer": reviewer
                }
            )

        return True

    def get_historical_metrics(
        self,
        period: str = "day",
        eval_type: Optional[EvalType] = None
    ) -> Dict[str, Any]:
        """Get historical quality metrics."""
        with self._lock:
            results = list(self._results)

        if eval_type:
            results = [r for r in results if r.eval_type == eval_type]

        if not results:
            return {"period": period, "data": []}

        # Group by period
        # Simplified: just return aggregate stats
        scores = [r.overall_score for r in results]
        passed = sum(1 for r in results if r.passed)

        return {
            "period": period,
            "total_evaluations": len(results),
            "pass_rate": passed / len(results) if results else 0.0,
            "average_score": statistics.mean(scores) if scores else 0.0,
            "score_std_dev": statistics.stdev(scores) if len(scores) > 1 else 0.0
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get evaluator statistics."""
        with self._lock:
            return {
                "registered_criteria": len(self._criteria),
                "test_cases": len(self._test_cases),
                "total_evaluations": len(self._results),
                "pending_reviews": len([
                    i for i in self._review_queue.values()
                    if i.status == ReviewStatus.PENDING
                ]),
                "has_llm_judge": self._llm_judge_fn is not None
            }


# Convenience exports
__all__ = [
    "AgentEvaluator",
    "EvalCriteria",
    "TestCase",
    "EvalScore",
    "EvalResult",
    "EvalReport",
    "QualityMetrics",
    "ReviewItem",
    "EvalType",
    "ScoreType",
    "ReviewStatus"
]
