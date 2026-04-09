#!/usr/bin/env python3
"""
Fallback Chain for LLM Model Degradation

Provides automatic fallback to simpler/cheaper models with:
- Configurable model chains
- Error-based fallback triggers
- Latency-based fallback
- Cost optimization
- Graceful degradation tracking
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

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


T = TypeVar("T")


class FallbackReason(Enum):
    """Reason for fallback."""
    ERROR = "error"                   # Model returned error
    TIMEOUT = "timeout"               # Model timed out
    RATE_LIMIT = "rate_limit"         # Hit rate limit
    COST_LIMIT = "cost_limit"         # Would exceed cost limit
    QUALITY = "quality"               # Output quality too low
    MANUAL = "manual"                 # Manually triggered


@dataclass
class ModelConfig:
    """Configuration for a model in the chain."""

    name: str                         # Model identifier (e.g., "claude-3-opus")
    timeout_seconds: float = 60.0     # Request timeout
    max_retries: int = 1              # Retries before fallback
    cost_per_1k_input: float = 0.0    # Cost per 1K input tokens
    cost_per_1k_output: float = 0.0   # Cost per 1K output tokens
    min_confidence: float = 0.0       # Minimum confidence threshold
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FallbackAttempt:
    """Record of a fallback attempt."""

    model: str
    success: bool
    reason: Optional[FallbackReason]
    latency_ms: float
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: _now_utc().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["reason"] = self.reason.value if self.reason else None
        return d


@dataclass
class FallbackResult(Generic[T]):
    """Result of a fallback chain execution."""

    success: bool
    result: Optional[T]
    final_model: str
    attempts: List[FallbackAttempt]
    total_latency_ms: float
    degraded: bool                    # True if fell back to lower model
    fallback_count: int               # Number of fallbacks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_model": self.final_model,
            "attempts": [a.to_dict() for a in self.attempts],
            "total_latency_ms": self.total_latency_ms,
            "degraded": self.degraded,
            "fallback_count": self.fallback_count,
        }


class AllModelsFailedError(Exception):
    """Raised when all models in the chain fail."""

    def __init__(self, attempts: List[FallbackAttempt]):
        self.attempts = attempts
        models = [a.model for a in attempts]
        super().__init__(f"All models failed: {models}")


class FallbackChain:
    """
    Automatic fallback chain for LLM models.

    Features:
    - Ordered model chain (best → fallback)
    - Multiple fallback triggers (error, timeout, rate limit)
    - Per-model configuration
    - Graceful degradation tracking
    - Cost optimization
    """

    # Default model chains for common providers
    CLAUDE_CHAIN = [
        ModelConfig("claude-3-opus", timeout_seconds=120, cost_per_1k_input=15.0, cost_per_1k_output=75.0),
        ModelConfig("claude-3-sonnet", timeout_seconds=60, cost_per_1k_input=3.0, cost_per_1k_output=15.0),
        ModelConfig("claude-3-haiku", timeout_seconds=30, cost_per_1k_input=0.25, cost_per_1k_output=1.25),
    ]

    GPT_CHAIN = [
        ModelConfig("gpt-4", timeout_seconds=120, cost_per_1k_input=30.0, cost_per_1k_output=60.0),
        ModelConfig("gpt-4-turbo", timeout_seconds=60, cost_per_1k_input=10.0, cost_per_1k_output=30.0),
        ModelConfig("gpt-3.5-turbo", timeout_seconds=30, cost_per_1k_input=0.5, cost_per_1k_output=1.5),
    ]

    def __init__(
        self,
        models: List[ModelConfig],
        on_fallback: Optional[Callable[[str, str, FallbackReason], None]] = None,
        on_all_failed: Optional[Callable[[List[FallbackAttempt]], None]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize fallback chain.

        Args:
            models: Ordered list of models (primary → fallbacks)
            on_fallback: Callback on fallback (from_model, to_model, reason)
            on_all_failed: Callback when all models fail
            ledger: Optional EventLogger for tracking
        """
        if not models:
            raise ValueError("At least one model required")

        self.models = models
        self.on_fallback = on_fallback
        self.on_all_failed = on_all_failed
        self.ledger = ledger

    def _get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get config for a model by name."""
        for model in self.models:
            if model.name == model_name:
                return model
        return None

    def _should_fallback(
        self,
        error: Optional[Exception],
        latency_ms: float,
        config: ModelConfig,
    ) -> Optional[FallbackReason]:
        """Determine if we should fallback and why."""
        if error is not None:
            error_str = str(error).lower()

            # Check for specific error types
            if "timeout" in error_str or "timed out" in error_str:
                return FallbackReason.TIMEOUT

            if "rate" in error_str and "limit" in error_str:
                return FallbackReason.RATE_LIMIT

            if "429" in error_str:
                return FallbackReason.RATE_LIMIT

            return FallbackReason.ERROR

        # Check timeout
        if latency_ms > config.timeout_seconds * 1000:
            return FallbackReason.TIMEOUT

        return None

    def _log_event(
        self,
        event_type: str,
        card_id: Optional[str],
        data: Dict[str, Any],
    ) -> None:
        """Log fallback event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"fallback.{event_type}",
                card_id=card_id,
                actor="fallback_chain",
                data=data,
            )

    def execute(
        self,
        func: Callable[[str], T],
        card_id: Optional[str] = None,
        start_model: Optional[str] = None,
    ) -> FallbackResult[T]:
        """
        Execute function with fallback chain.

        The function receives the model name and should use it for the LLM call.

        Args:
            func: Function that takes model name and returns result
            card_id: Optional card ID for logging
            start_model: Optional model to start with (default: first in chain)

        Returns:
            FallbackResult with outcome

        Raises:
            AllModelsFailedError: If all models fail
        """
        attempts: List[FallbackAttempt] = []
        start_time = time.monotonic()

        # Determine starting index
        start_idx = 0
        if start_model:
            for i, model in enumerate(self.models):
                if model.name == start_model:
                    start_idx = i
                    break

        # Try models in order
        for i in range(start_idx, len(self.models)):
            config = self.models[i]
            attempt_start = time.monotonic()

            try:
                result = func(config.name)
                latency_ms = (time.monotonic() - attempt_start) * 1000

                # Success
                attempts.append(FallbackAttempt(
                    model=config.name,
                    success=True,
                    reason=None,
                    latency_ms=latency_ms,
                ))

                total_latency = (time.monotonic() - start_time) * 1000
                degraded = i > start_idx

                self._log_event("success", card_id, {
                    "model": config.name,
                    "degraded": degraded,
                    "fallback_count": i - start_idx,
                    "latency_ms": latency_ms,
                })

                return FallbackResult(
                    success=True,
                    result=result,
                    final_model=config.name,
                    attempts=attempts,
                    total_latency_ms=total_latency,
                    degraded=degraded,
                    fallback_count=i - start_idx,
                )

            except Exception as e:
                latency_ms = (time.monotonic() - attempt_start) * 1000
                reason = self._should_fallback(e, latency_ms, config)

                attempts.append(FallbackAttempt(
                    model=config.name,
                    success=False,
                    reason=reason,
                    latency_ms=latency_ms,
                    error=str(e),
                ))

                # Check if we can fallback
                if i < len(self.models) - 1:
                    next_model = self.models[i + 1].name

                    self._log_event("fallback", card_id, {
                        "from_model": config.name,
                        "to_model": next_model,
                        "reason": reason.value if reason else "error",
                        "error": str(e),
                    })

                    if self.on_fallback:
                        self.on_fallback(
                            config.name,
                            next_model,
                            reason or FallbackReason.ERROR,
                        )

        # All models failed
        total_latency = (time.monotonic() - start_time) * 1000

        self._log_event("all_failed", card_id, {
            "attempts": len(attempts),
            "total_latency_ms": total_latency,
        })

        if self.on_all_failed:
            self.on_all_failed(attempts)

        raise AllModelsFailedError(attempts)

    def execute_with_quality_check(
        self,
        func: Callable[[str], T],
        quality_check: Callable[[T], float],
        min_quality: float = 0.5,
        card_id: Optional[str] = None,
    ) -> FallbackResult[T]:
        """
        Execute with quality-based fallback.

        Falls back if output quality is below threshold.

        Args:
            func: Function that takes model name and returns result
            quality_check: Function that scores result (0-1)
            min_quality: Minimum acceptable quality score
            card_id: Optional card ID for logging

        Returns:
            FallbackResult with outcome
        """
        attempts: List[FallbackAttempt] = []
        start_time = time.monotonic()
        best_result: Optional[T] = None
        best_quality = 0.0
        best_model = ""

        for i, config in enumerate(self.models):
            attempt_start = time.monotonic()

            try:
                result = func(config.name)
                latency_ms = (time.monotonic() - attempt_start) * 1000

                # Check quality
                quality = quality_check(result)

                if quality >= min_quality:
                    # Good enough
                    attempts.append(FallbackAttempt(
                        model=config.name,
                        success=True,
                        reason=None,
                        latency_ms=latency_ms,
                    ))

                    total_latency = (time.monotonic() - start_time) * 1000

                    self._log_event("success", card_id, {
                        "model": config.name,
                        "quality": quality,
                        "degraded": i > 0,
                    })

                    return FallbackResult(
                        success=True,
                        result=result,
                        final_model=config.name,
                        attempts=attempts,
                        total_latency_ms=total_latency,
                        degraded=i > 0,
                        fallback_count=i,
                    )

                # Track best so far
                if quality > best_quality:
                    best_quality = quality
                    best_result = result
                    best_model = config.name

                # Quality too low, try next
                attempts.append(FallbackAttempt(
                    model=config.name,
                    success=False,
                    reason=FallbackReason.QUALITY,
                    latency_ms=latency_ms,
                    error=f"Quality {quality:.2f} below threshold {min_quality}",
                ))

                self._log_event("quality_fallback", card_id, {
                    "model": config.name,
                    "quality": quality,
                    "threshold": min_quality,
                })

            except Exception as e:
                latency_ms = (time.monotonic() - attempt_start) * 1000

                attempts.append(FallbackAttempt(
                    model=config.name,
                    success=False,
                    reason=FallbackReason.ERROR,
                    latency_ms=latency_ms,
                    error=str(e),
                ))

        # Return best result if we have one
        if best_result is not None:
            total_latency = (time.monotonic() - start_time) * 1000

            return FallbackResult(
                success=True,
                result=best_result,
                final_model=best_model,
                attempts=attempts,
                total_latency_ms=total_latency,
                degraded=True,
                fallback_count=len(attempts),
            )

        raise AllModelsFailedError(attempts)

    def get_cheapest_model(self) -> ModelConfig:
        """Get the cheapest model in the chain."""
        return min(
            self.models,
            key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output,
        )

    def get_fastest_model(self) -> ModelConfig:
        """Get the model with shortest timeout (assumed fastest)."""
        return min(self.models, key=lambda m: m.timeout_seconds)

    def estimate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a model call."""
        config = self._get_model_config(model_name)
        if not config:
            return 0.0

        input_cost = (input_tokens / 1000) * config.cost_per_1k_input
        output_cost = (output_tokens / 1000) * config.cost_per_1k_output
        return input_cost + output_cost


# Convenience factory functions
def create_claude_chain(
    ledger: Optional[EventLogger] = None,
) -> FallbackChain:
    """Create a Claude model fallback chain."""
    return FallbackChain(models=FallbackChain.CLAUDE_CHAIN, ledger=ledger)


def create_gpt_chain(
    ledger: Optional[EventLogger] = None,
) -> FallbackChain:
    """Create a GPT model fallback chain."""
    return FallbackChain(models=FallbackChain.GPT_CHAIN, ledger=ledger)


def create_cost_optimized_chain(
    models: List[ModelConfig],
    ledger: Optional[EventLogger] = None,
) -> FallbackChain:
    """Create a chain ordered by cost (cheapest first)."""
    sorted_models = sorted(
        models,
        key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output,
    )
    return FallbackChain(models=sorted_models, ledger=ledger)
