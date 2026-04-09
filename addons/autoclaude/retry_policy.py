#!/usr/bin/env python3
"""
Retry Policy with Exponential Backoff

Provides robust retry logic for LLM operations with:
- Configurable backoff strategies
- Jitter to prevent thundering herd
- Per-exception retry rules
- Integration with circuit breaker
"""

from __future__ import annotations

import asyncio
import functools
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

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


class BackoffStrategy(Enum):
    """Backoff calculation strategies."""
    CONSTANT = "constant"           # Same delay each time
    LINEAR = "linear"               # Delay increases linearly
    EXPONENTIAL = "exponential"     # Delay doubles each time
    FIBONACCI = "fibonacci"         # Delay follows Fibonacci sequence


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        total_delay: float,
        last_exception: Optional[Exception] = None,
    ):
        self.attempts = attempts
        self.total_delay = total_delay
        self.last_exception = last_exception
        super().__init__(message)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["retryable_exceptions"] = [e.__name__ for e in self.retryable_exceptions]
        d["non_retryable_exceptions"] = [e.__name__ for e in self.non_retryable_exceptions]
        return d


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt: int
    timestamp: str
    success: bool
    delay_before: float
    duration_ms: float
    error: Optional[str] = None
    error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any
    attempts: List[RetryAttempt]
    total_attempts: int
    total_delay: float
    total_duration_ms: float
    final_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "success": self.success,
            "total_attempts": self.total_attempts,
            "total_delay": self.total_delay,
            "total_duration_ms": self.total_duration_ms,
            "final_error": self.final_error,
            "attempts": [a.to_dict() for a in self.attempts],
        }
        return d


class RetryPolicy:
    """
    Retry policy with configurable backoff strategies.

    Features:
    - Multiple backoff strategies (constant, linear, exponential, fibonacci)
    - Jitter to prevent thundering herd
    - Exception-based retry rules
    - Sync and async support
    - Detailed attempt tracking
    """

    # Fibonacci sequence for backoff
    _FIB_SEQUENCE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize retry policy.

        Args:
            config: Retry configuration
            ledger: Optional EventLogger for logging retry attempts
        """
        self.config = config or RetryConfig()
        self.ledger = ledger

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for an attempt."""
        strategy = self.config.strategy
        base = self.config.base_delay

        if strategy == BackoffStrategy.CONSTANT:
            delay = base

        elif strategy == BackoffStrategy.LINEAR:
            delay = base * attempt

        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base * (self.config.exponential_base ** (attempt - 1))

        elif strategy == BackoffStrategy.FIBONACCI:
            fib_index = min(attempt - 1, len(self._FIB_SEQUENCE) - 1)
            delay = base * self._FIB_SEQUENCE[fib_index]

        else:
            delay = base

        # Apply max delay cap
        delay = min(delay, self.config.max_delay)

        # Apply jitter
        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # Ensure non-negative

        return delay

    def _should_retry(self, exception: Exception) -> bool:
        """Check if exception should trigger a retry."""
        # Check non-retryable first (takes precedence)
        if self.config.non_retryable_exceptions:
            if isinstance(exception, self.config.non_retryable_exceptions):
                return False

        # Check retryable
        if self.config.retryable_exceptions:
            return isinstance(exception, self.config.retryable_exceptions)

        return True

    def _log_event(
        self,
        event_type: str,
        card_id: Optional[str],
        data: Dict[str, Any],
    ) -> None:
        """Log retry event to ledger."""
        if self.ledger:
            self.ledger.log(
                event_type=f"retry.{event_type}",
                card_id=card_id,
                actor="retry_policy",
                data=data,
            )

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        card_id: Optional[str] = None,
        **kwargs: Any,
    ) -> RetryResult:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            card_id: Optional card ID for logging
            **kwargs: Keyword arguments for function

        Returns:
            RetryResult with outcome and attempt details

        Raises:
            RetryExhaustedError: If all attempts fail
        """
        attempts: List[RetryAttempt] = []
        total_delay = 0.0
        start_time = time.monotonic()
        last_exception: Optional[Exception] = None

        for attempt_num in range(1, self.config.max_attempts + 1):
            # Calculate delay (no delay for first attempt)
            if attempt_num > 1:
                delay = self._calculate_delay(attempt_num)
                total_delay += delay
                time.sleep(delay)
            else:
                delay = 0.0

            attempt_start = time.monotonic()

            try:
                result = func(*args, **kwargs)

                # Success
                duration_ms = (time.monotonic() - attempt_start) * 1000
                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    timestamp=_now_utc().isoformat(),
                    success=True,
                    delay_before=delay,
                    duration_ms=duration_ms,
                ))

                total_duration = (time.monotonic() - start_time) * 1000

                self._log_event("success", card_id, {
                    "attempt": attempt_num,
                    "total_attempts": attempt_num,
                    "total_delay": total_delay,
                })

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_attempts=attempt_num,
                    total_delay=total_delay,
                    total_duration_ms=total_duration,
                )

            except Exception as e:
                last_exception = e
                duration_ms = (time.monotonic() - attempt_start) * 1000

                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    timestamp=_now_utc().isoformat(),
                    success=False,
                    delay_before=delay,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

                # Check if we should retry
                if not self._should_retry(e):
                    self._log_event("non_retryable", card_id, {
                        "attempt": attempt_num,
                        "error_type": type(e).__name__,
                        "error": str(e),
                    })
                    break

                # Log retry attempt
                if attempt_num < self.config.max_attempts:
                    self._log_event("attempt_failed", card_id, {
                        "attempt": attempt_num,
                        "error_type": type(e).__name__,
                        "next_delay": self._calculate_delay(attempt_num + 1),
                    })

        # All attempts exhausted
        total_duration = (time.monotonic() - start_time) * 1000

        self._log_event("exhausted", card_id, {
            "total_attempts": len(attempts),
            "total_delay": total_delay,
            "final_error": str(last_exception) if last_exception else None,
        })

        error_msg = f"Retry exhausted after {len(attempts)} attempts"
        raise RetryExhaustedError(
            error_msg,
            attempts=len(attempts),
            total_delay=total_delay,
            last_exception=last_exception,
        )

    async def execute_async(
        self,
        func: Callable[..., T],
        *args: Any,
        card_id: Optional[str] = None,
        **kwargs: Any,
    ) -> RetryResult:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            card_id: Optional card ID for logging
            **kwargs: Keyword arguments for function

        Returns:
            RetryResult with outcome and attempt details

        Raises:
            RetryExhaustedError: If all attempts fail
        """
        attempts: List[RetryAttempt] = []
        total_delay = 0.0
        start_time = time.monotonic()
        last_exception: Optional[Exception] = None

        for attempt_num in range(1, self.config.max_attempts + 1):
            # Calculate delay (no delay for first attempt)
            if attempt_num > 1:
                delay = self._calculate_delay(attempt_num)
                total_delay += delay
                await asyncio.sleep(delay)
            else:
                delay = 0.0

            attempt_start = time.monotonic()

            try:
                result = await func(*args, **kwargs)

                # Success
                duration_ms = (time.monotonic() - attempt_start) * 1000
                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    timestamp=_now_utc().isoformat(),
                    success=True,
                    delay_before=delay,
                    duration_ms=duration_ms,
                ))

                total_duration = (time.monotonic() - start_time) * 1000

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_attempts=attempt_num,
                    total_delay=total_delay,
                    total_duration_ms=total_duration,
                )

            except Exception as e:
                last_exception = e
                duration_ms = (time.monotonic() - attempt_start) * 1000

                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    timestamp=_now_utc().isoformat(),
                    success=False,
                    delay_before=delay,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

                if not self._should_retry(e):
                    break

        total_duration = (time.monotonic() - start_time) * 1000

        error_msg = f"Retry exhausted after {len(attempts)} attempts"
        raise RetryExhaustedError(
            error_msg,
            attempts=len(attempts),
            total_delay=total_delay,
            last_exception=last_exception,
        )

    def decorator(
        self,
        card_id: Optional[str] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Create a decorator that applies retry logic.

        Args:
            card_id: Optional card ID for logging

        Returns:
            Decorator function
        """
        def _decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def _wrapper(*args: Any, **kwargs: Any) -> T:
                result = self.execute(func, *args, card_id=card_id, **kwargs)
                return result.result
            return _wrapper
        return _decorator

    def async_decorator(
        self,
        card_id: Optional[str] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Create a decorator that applies async retry logic.

        Args:
            card_id: Optional card ID for logging

        Returns:
            Async decorator function
        """
        def _decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            async def _wrapper(*args: Any, **kwargs: Any) -> T:
                result = await self.execute_async(func, *args, card_id=card_id, **kwargs)
                return result.result
            return _wrapper
        return _decorator


# Convenience function for common LLM retry scenarios
def llm_retry_policy(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    ledger: Optional[EventLogger] = None,
) -> RetryPolicy:
    """
    Create a retry policy optimized for LLM API calls.

    Handles common transient errors:
    - Rate limiting (429)
    - Server errors (5xx)
    - Timeout errors
    - Connection errors

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        ledger: Optional event logger

    Returns:
        Configured RetryPolicy
    """
    # Common transient LLM API exceptions
    retryable = (
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionRefusedError,
    )

    # Try to add httpx/aiohttp exceptions if available
    try:
        import httpx
        retryable = retryable + (httpx.TimeoutException, httpx.NetworkError)
    except ImportError:
        pass

    try:
        import aiohttp
        retryable = retryable + (aiohttp.ClientError,)
    except ImportError:
        pass

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=60.0,
        strategy=BackoffStrategy.EXPONENTIAL,
        exponential_base=2.0,
        jitter=True,
        jitter_factor=0.2,
        retryable_exceptions=retryable,
    )

    return RetryPolicy(config=config, ledger=ledger)
