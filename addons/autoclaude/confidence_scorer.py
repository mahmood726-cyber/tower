#!/usr/bin/env python3
"""
Confidence Scoring for LLM Outputs

Provides confidence assessment for LLM outputs with:
- Multiple scoring heuristics
- Threshold-based routing
- Calibration support
- Historical confidence tracking
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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


class ConfidenceLevel(Enum):
    """Discrete confidence levels."""
    HIGH = "HIGH"           # > 0.8 - Proceed automatically
    MEDIUM = "MEDIUM"       # 0.5 - 0.8 - Proceed with monitoring
    LOW = "LOW"             # 0.3 - 0.5 - Requires human review
    VERY_LOW = "VERY_LOW"   # < 0.3 - Reject or escalate


@dataclass
class ConfidenceResult:
    """Result of confidence assessment."""

    score: float                        # 0.0 to 1.0
    level: ConfidenceLevel
    components: Dict[str, float]        # Individual scorer contributions
    reasoning: List[str]                # Human-readable explanations
    should_proceed: bool                # Recommended action
    requires_review: bool               # Whether human review needed
    timestamp: str = field(default_factory=lambda: _now_utc().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value
        return d


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring."""

    # Thresholds
    high_threshold: float = 0.8
    medium_threshold: float = 0.5
    low_threshold: float = 0.3

    # Weights for component scores
    weights: Dict[str, float] = field(default_factory=lambda: {
        "completion_quality": 0.3,
        "response_structure": 0.2,
        "uncertainty_markers": 0.2,
        "consistency": 0.15,
        "length_appropriateness": 0.15,
    })

    # Auto-proceed threshold
    auto_proceed_threshold: float = 0.7

    # Force review threshold
    force_review_threshold: float = 0.4

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfidenceScorer:
    """
    Confidence scoring for LLM outputs.

    Features:
    - Multiple heuristic scorers
    - Configurable weights and thresholds
    - Threshold-based routing recommendations
    - Calibration with historical outcomes
    - Integration with human checkpoints
    """

    # Patterns indicating uncertainty
    UNCERTAINTY_PATTERNS = [
        r'\b(i think|i believe|probably|possibly|maybe|might|could be|not sure|uncertain)\b',
        r'\b(i\'m not certain|i don\'t know|it\'s unclear|it depends)\b',
        r'\b(approximately|roughly|about|around|estimated)\b',
        r'\?\s*$',  # Ending with question mark
    ]

    # Patterns indicating confidence
    CONFIDENCE_PATTERNS = [
        r'\b(definitely|certainly|absolutely|clearly|obviously)\b',
        r'\b(the answer is|this is|here is|the solution)\b',
        r'\b(confirmed|verified|validated|correct)\b',
    ]

    # Structural elements that indicate quality
    STRUCTURE_PATTERNS = [
        r'^#{1,3}\s+\w+',  # Markdown headers
        r'^\d+\.\s+\w+',   # Numbered lists
        r'^[-*]\s+\w+',    # Bullet points
        r'```[\w]*\n',     # Code blocks
    ]

    def __init__(
        self,
        config: Optional[ConfidenceConfig] = None,
        custom_scorers: Optional[Dict[str, Callable[[str, Dict], float]]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize confidence scorer.

        Args:
            config: Scoring configuration
            custom_scorers: Additional custom scoring functions
            ledger: Optional EventLogger for tracking
        """
        self.config = config or ConfidenceConfig()
        self.custom_scorers = custom_scorers or {}
        self.ledger = ledger

        # Compile patterns
        self._uncertainty_re = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.UNCERTAINTY_PATTERNS
        ]
        self._confidence_re = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.CONFIDENCE_PATTERNS
        ]
        self._structure_re = [
            re.compile(p, re.MULTILINE)
            for p in self.STRUCTURE_PATTERNS
        ]

        # Calibration history
        self._calibration_data: List[Tuple[float, bool]] = []

    def _score_completion_quality(
        self,
        output: str,
        context: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score based on completion quality indicators.

        Checks for:
        - Completeness (not truncated)
        - No error messages
        - Proper conclusion
        """
        score = 1.0
        reasons = []

        # Check for truncation indicators
        truncation_markers = [
            "...",
            "[truncated]",
            "[continued]",
            "I'll continue",
        ]
        for marker in truncation_markers:
            if marker.lower() in output.lower()[-100:]:
                score -= 0.3
                reasons.append("Possible truncation detected")
                break

        # Check for error indicators
        error_markers = [
            "error:",
            "exception:",
            "failed to",
            "unable to",
            "i cannot",
            "i'm unable",
        ]
        for marker in error_markers:
            if marker.lower() in output.lower():
                score -= 0.2
                reasons.append("Error indicators present")
                break

        # Check for proper conclusion
        conclusion_markers = [
            "in summary",
            "to conclude",
            "in conclusion",
            "therefore",
            "thus",
        ]
        has_conclusion = any(
            marker in output.lower()
            for marker in conclusion_markers
        )
        if has_conclusion:
            score += 0.1
            reasons.append("Has proper conclusion")

        reasoning = "; ".join(reasons) if reasons else "Standard completion"
        return max(0.0, min(1.0, score)), reasoning

    def _score_response_structure(
        self,
        output: str,
        context: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score based on response structure.

        Checks for:
        - Organized formatting
        - Code blocks where appropriate
        - Lists and headers
        """
        score = 0.5  # Baseline
        reasons = []

        # Count structural elements
        structure_count = 0
        for pattern in self._structure_re:
            matches = len(pattern.findall(output))
            structure_count += matches

        if structure_count > 5:
            score += 0.4
            reasons.append("Well-structured response")
        elif structure_count > 2:
            score += 0.2
            reasons.append("Some structure present")
        elif structure_count == 0 and len(output) > 500:
            score -= 0.2
            reasons.append("Long response lacks structure")

        # Check if code expected and present
        if context.get("expects_code", False):
            if "```" in output:
                score += 0.2
                reasons.append("Contains expected code blocks")
            else:
                score -= 0.3
                reasons.append("Missing expected code")

        reasoning = "; ".join(reasons) if reasons else "Standard structure"
        return max(0.0, min(1.0, score)), reasoning

    def _score_uncertainty_markers(
        self,
        output: str,
        context: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score based on uncertainty language.

        Fewer uncertainty markers = higher confidence.
        More confidence markers = higher confidence.
        """
        # Count uncertainty markers
        uncertainty_count = 0
        for pattern in self._uncertainty_re:
            uncertainty_count += len(pattern.findall(output))

        # Count confidence markers
        confidence_count = 0
        for pattern in self._confidence_re:
            confidence_count += len(pattern.findall(output))

        # Normalize by length (per 100 words)
        word_count = len(output.split())
        if word_count > 0:
            uncertainty_rate = (uncertainty_count / word_count) * 100
            confidence_rate = (confidence_count / word_count) * 100
        else:
            uncertainty_rate = 0
            confidence_rate = 0

        # Calculate score
        # High uncertainty = low score, high confidence = high score
        score = 0.7  # Baseline
        reasons = []

        if uncertainty_rate > 5:
            score -= 0.3
            reasons.append(f"High uncertainty language ({uncertainty_count} markers)")
        elif uncertainty_rate > 2:
            score -= 0.1
            reasons.append(f"Some uncertainty language ({uncertainty_count} markers)")

        if confidence_rate > 3:
            score += 0.2
            reasons.append(f"Strong confidence language ({confidence_count} markers)")
        elif confidence_rate > 1:
            score += 0.1
            reasons.append(f"Some confidence language ({confidence_count} markers)")

        reasoning = "; ".join(reasons) if reasons else "Neutral language"
        return max(0.0, min(1.0, score)), reasoning

    def _score_consistency(
        self,
        output: str,
        context: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score based on internal consistency.

        Checks for:
        - Contradictory statements
        - Consistent terminology
        - Logical flow
        """
        score = 0.8  # High baseline - hard to detect inconsistency
        reasons = []

        # Check for contradiction markers
        contradiction_patterns = [
            r'but actually',
            r'on second thought',
            r'wait,? (no|actually)',
            r'i mean',
            r'correction:',
            r'let me reconsider',
        ]

        for pattern in contradiction_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                score -= 0.2
                reasons.append("Self-correction detected")
                break

        # Check for repeated questions (confusion indicator)
        question_count = output.count("?")
        if question_count > 3:
            score -= 0.1
            reasons.append("Multiple questions in response")

        reasoning = "; ".join(reasons) if reasons else "Consistent response"
        return max(0.0, min(1.0, score)), reasoning

    def _score_length_appropriateness(
        self,
        output: str,
        context: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Score based on response length appropriateness.

        Too short = possibly incomplete
        Too long = possibly rambling
        """
        word_count = len(output.split())
        expected_min = context.get("expected_min_words", 10)
        expected_max = context.get("expected_max_words", 2000)

        if word_count < expected_min:
            score = 0.3
            reasoning = f"Response too short ({word_count} words)"
        elif word_count > expected_max:
            score = 0.5
            reasoning = f"Response very long ({word_count} words)"
        elif word_count < expected_min * 2:
            score = 0.7
            reasoning = f"Response relatively short ({word_count} words)"
        else:
            score = 0.9
            reasoning = f"Appropriate length ({word_count} words)"

        return score, reasoning

    def _get_level(self, score: float) -> ConfidenceLevel:
        """Map score to confidence level."""
        if score >= self.config.high_threshold:
            return ConfidenceLevel.HIGH
        elif score >= self.config.medium_threshold:
            return ConfidenceLevel.MEDIUM
        elif score >= self.config.low_threshold:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def score(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
        card_id: Optional[str] = None,
    ) -> ConfidenceResult:
        """
        Score confidence in an LLM output.

        Args:
            output: The LLM output to score
            context: Optional context about the expected response
            card_id: Optional card ID for logging

        Returns:
            ConfidenceResult with score and recommendations
        """
        context = context or {}
        components: Dict[str, float] = {}
        reasoning: List[str] = []

        # Run built-in scorers
        scorers = {
            "completion_quality": self._score_completion_quality,
            "response_structure": self._score_response_structure,
            "uncertainty_markers": self._score_uncertainty_markers,
            "consistency": self._score_consistency,
            "length_appropriateness": self._score_length_appropriateness,
        }

        for name, scorer in scorers.items():
            score, reason = scorer(output, context)
            components[name] = score
            reasoning.append(f"{name}: {reason}")

        # Run custom scorers
        for name, scorer in self.custom_scorers.items():
            try:
                score = scorer(output, context)
                components[name] = max(0.0, min(1.0, score))
            except Exception as e:
                components[name] = 0.5  # Neutral on error
                reasoning.append(f"{name}: error - {e}")

        # Calculate weighted score
        weights = self.config.weights
        total_weight = 0.0
        weighted_sum = 0.0

        for name, score in components.items():
            weight = weights.get(name, 0.1)  # Default weight for custom scorers
            weighted_sum += score * weight
            total_weight += weight

        final_score = weighted_sum / total_weight if total_weight > 0 else 0.5

        # Determine level and recommendations
        level = self._get_level(final_score)
        should_proceed = final_score >= self.config.auto_proceed_threshold
        requires_review = final_score < self.config.force_review_threshold

        result = ConfidenceResult(
            score=round(final_score, 3),
            level=level,
            components=components,
            reasoning=reasoning,
            should_proceed=should_proceed,
            requires_review=requires_review,
        )

        # Log if ledger available
        if self.ledger and card_id:
            self.ledger.log(
                event_type="confidence.scored",
                card_id=card_id,
                actor="confidence_scorer",
                data={
                    "score": result.score,
                    "level": level.value,
                    "should_proceed": should_proceed,
                    "requires_review": requires_review,
                },
            )

        return result

    def record_outcome(
        self,
        score: float,
        success: bool,
    ) -> None:
        """
        Record outcome for calibration.

        Args:
            score: The confidence score that was given
            success: Whether the output was actually successful
        """
        self._calibration_data.append((score, success))

        # Keep last 1000 for memory efficiency
        if len(self._calibration_data) > 1000:
            self._calibration_data = self._calibration_data[-1000:]

    def get_calibration_stats(self) -> Dict[str, Any]:
        """
        Get calibration statistics.

        Returns:
            Dict with calibration metrics
        """
        if not self._calibration_data:
            return {"message": "No calibration data available"}

        # Bin scores into ranges
        bins = {
            "0.0-0.2": {"count": 0, "successes": 0},
            "0.2-0.4": {"count": 0, "successes": 0},
            "0.4-0.6": {"count": 0, "successes": 0},
            "0.6-0.8": {"count": 0, "successes": 0},
            "0.8-1.0": {"count": 0, "successes": 0},
        }

        for score, success in self._calibration_data:
            if score < 0.2:
                bin_key = "0.0-0.2"
            elif score < 0.4:
                bin_key = "0.2-0.4"
            elif score < 0.6:
                bin_key = "0.4-0.6"
            elif score < 0.8:
                bin_key = "0.6-0.8"
            else:
                bin_key = "0.8-1.0"

            bins[bin_key]["count"] += 1
            if success:
                bins[bin_key]["successes"] += 1

        # Calculate accuracy per bin
        for bin_key in bins:
            count = bins[bin_key]["count"]
            if count > 0:
                bins[bin_key]["accuracy"] = bins[bin_key]["successes"] / count
            else:
                bins[bin_key]["accuracy"] = None

        # Overall calibration error (Brier score)
        brier_sum = 0.0
        for score, success in self._calibration_data:
            outcome = 1.0 if success else 0.0
            brier_sum += (score - outcome) ** 2

        brier_score = brier_sum / len(self._calibration_data)

        return {
            "total_samples": len(self._calibration_data),
            "bins": bins,
            "brier_score": round(brier_score, 4),
            "calibration_quality": "good" if brier_score < 0.1 else "needs_adjustment",
        }

    def suggest_threshold_adjustment(self) -> Dict[str, float]:
        """
        Suggest threshold adjustments based on calibration data.

        Returns:
            Dict with suggested thresholds
        """
        stats = self.get_calibration_stats()

        if "message" in stats:
            return {
                "message": "Insufficient data for suggestions",
                "current": self.config.to_dict(),
            }

        bins = stats["bins"]
        suggestions = {}

        # Find score range with ~90% accuracy for high threshold
        for bin_key in ["0.8-1.0", "0.6-0.8", "0.4-0.6"]:
            if bins[bin_key]["accuracy"] and bins[bin_key]["accuracy"] >= 0.9:
                lower = float(bin_key.split("-")[0])
                suggestions["high_threshold"] = lower
                break
        else:
            suggestions["high_threshold"] = 0.9  # Be more conservative

        # Find score range with ~50% accuracy for medium threshold
        for bin_key in ["0.4-0.6", "0.2-0.4"]:
            if bins[bin_key]["accuracy"] and bins[bin_key]["accuracy"] >= 0.5:
                lower = float(bin_key.split("-")[0])
                suggestions["medium_threshold"] = lower
                break
        else:
            suggestions["medium_threshold"] = 0.6

        return suggestions
