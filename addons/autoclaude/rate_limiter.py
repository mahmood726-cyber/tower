#!/usr/bin/env python3
"""
Rate Limiter with Token Bucket Algorithm

Provides rate limiting for LLM API calls with:
- Token bucket algorithm for smooth rate limiting
- Per-model and per-card limits
- Sliding window tracking
- Async support
- Burst handling
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

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


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded and blocking is disabled."""

    def __init__(
        self,
        limit_name: str,
        tokens_requested: float,
        tokens_available: float,
        retry_after_seconds: float,
    ):
        self.limit_name = limit_name
        self.tokens_requested = tokens_requested
        self.tokens_available = tokens_available
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Rate limit '{limit_name}' exceeded: "
            f"requested {tokens_requested}, available {tokens_available}, "
            f"retry after {retry_after_seconds:.2f}s"
        )


class LimitScope(Enum):
    """Scope of rate limit."""
    GLOBAL = "global"           # Applies to all requests
    PER_MODEL = "per_model"     # Per-model limits
    PER_CARD = "per_card"       # Per-card limits
    PER_USER = "per_user"       # Per-user limits


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""

    name: str                           # Limit identifier
    tokens_per_second: float            # Token refill rate
    bucket_size: float                  # Maximum tokens in bucket
    scope: LimitScope = LimitScope.GLOBAL
    initial_tokens: Optional[float] = None  # Initial tokens (default: bucket_size)
    min_tokens: float = 1.0             # Minimum tokens per request

    def __post_init__(self):
        if self.initial_tokens is None:
            self.initial_tokens = self.bucket_size


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    config: RateLimitConfig
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        if self.tokens == 0.0:
            self.tokens = self.config.initial_tokens or self.config.bucket_size

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(
            self.config.bucket_size,
            self.tokens + elapsed * self.config.tokens_per_second,
        )
        self.last_update = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without blocking.

        Returns True if tokens were acquired, False otherwise.
        """
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def acquire_blocking(self, tokens: float = 1.0, timeout: float = 30.0) -> bool:
        """
        Acquire tokens, blocking until available or timeout.

        Returns True if tokens were acquired, False on timeout.
        """
        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.config.tokens_per_second

            # Check timeout
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            # Wait for tokens to refill
            time.sleep(min(wait_time, remaining, 0.1))

    async def acquire_async(self, tokens: float = 1.0, timeout: float = 30.0) -> bool:
        """
        Acquire tokens asynchronously.

        Returns True if tokens were acquired, False on timeout.
        """
        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.config.tokens_per_second

            # Check timeout
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            # Wait for tokens to refill
            await asyncio.sleep(min(wait_time, remaining, 0.1))

    def get_available_tokens(self) -> float:
        """Get currently available tokens."""
        with self._lock:
            self._refill()
            return self.tokens

    def time_until_available(self, tokens: float = 1.0) -> float:
        """Get time in seconds until tokens are available."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.config.tokens_per_second

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.config.name,
            "tokens": self.tokens,
            "bucket_size": self.config.bucket_size,
            "tokens_per_second": self.config.tokens_per_second,
            "scope": self.config.scope.value,
        }


@dataclass
class RateLimitStats:
    """Statistics for rate limiting."""

    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    total_wait_time_ms: float = 0.0
    tokens_consumed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RateLimiter:
    """
    Rate limiter with token bucket algorithm.

    Features:
    - Multiple named rate limits
    - Per-scope buckets (global, per-model, per-card)
    - Blocking and non-blocking modes
    - Async support
    - Statistics tracking
    """

    # Default rate limits for common scenarios
    DEFAULT_LIMITS = [
        RateLimitConfig(
            name="api_calls",
            tokens_per_second=10.0,      # 10 requests/second
            bucket_size=60.0,            # Burst of 60
            scope=LimitScope.GLOBAL,
        ),
        RateLimitConfig(
            name="tokens_per_minute",
            tokens_per_second=10000.0,   # 600K tokens/minute
            bucket_size=100000.0,        # Burst of 100K
            scope=LimitScope.GLOBAL,
        ),
    ]

    CLAUDE_LIMITS = [
        RateLimitConfig(
            name="claude_api",
            tokens_per_second=1.0,       # 1 request/second (conservative)
            bucket_size=10.0,            # Burst of 10
            scope=LimitScope.GLOBAL,
        ),
        RateLimitConfig(
            name="claude_tokens",
            tokens_per_second=5000.0,    # 300K tokens/minute
            bucket_size=50000.0,         # Burst of 50K
            scope=LimitScope.GLOBAL,
        ),
    ]

    def __init__(
        self,
        limits: Optional[List[RateLimitConfig]] = None,
        ledger: Optional[EventLogger] = None,
        on_limit_exceeded: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            limits: List of rate limit configurations
            ledger: Optional EventLogger for tracking
            on_limit_exceeded: Callback when limit is exceeded (name, wait_time)
        """
        self.limits = limits or self.DEFAULT_LIMITS
        self.ledger = ledger
        self.on_limit_exceeded = on_limit_exceeded

        # Create buckets for each limit
        self._global_buckets: Dict[str, TokenBucket] = {}
        self._scoped_buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self._stats: Dict[str, RateLimitStats] = {}

        for limit in self.limits:
            if limit.scope == LimitScope.GLOBAL:
                self._global_buckets[limit.name] = TokenBucket(config=limit)
            else:
                self._scoped_buckets[limit.name] = {}
            self._stats[limit.name] = RateLimitStats()

        self._lock = threading.Lock()

    def _get_bucket(
        self,
        limit: RateLimitConfig,
        scope_key: Optional[str] = None,
    ) -> TokenBucket:
        """Get or create bucket for a limit."""
        if limit.scope == LimitScope.GLOBAL:
            return self._global_buckets[limit.name]

        # Scoped bucket
        if scope_key is None:
            scope_key = "__default__"

        with self._lock:
            if limit.name not in self._scoped_buckets:
                self._scoped_buckets[limit.name] = {}

            buckets = self._scoped_buckets[limit.name]
            if scope_key not in buckets:
                buckets[scope_key] = TokenBucket(config=limit)

            return buckets[scope_key]

    def _get_scope_key(
        self,
        limit: RateLimitConfig,
        model: Optional[str] = None,
        card_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get scope key based on limit scope."""
        if limit.scope == LimitScope.GLOBAL:
            return None
        elif limit.scope == LimitScope.PER_MODEL:
            return model or "__default__"
        elif limit.scope == LimitScope.PER_CARD:
            return card_id or "__default__"
        elif limit.scope == LimitScope.PER_USER:
            return user_id or "__default__"
        return None

    def _log_event(
        self,
        event_type: str,
        limit_name: str,
        data: Dict[str, Any],
    ) -> None:
        """Log rate limit event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"rate_limit.{event_type}",
                card_id=data.get("card_id"),
                actor="rate_limiter",
                data={"limit": limit_name, **data},
            )

    def try_acquire(
        self,
        limit_name: Optional[str] = None,
        tokens: float = 1.0,
        model: Optional[str] = None,
        card_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            limit_name: Specific limit to check (None = all limits)
            tokens: Number of tokens to acquire
            model: Model name for per-model limits
            card_id: Card ID for per-card limits
            user_id: User ID for per-user limits

        Returns:
            True if tokens acquired from all applicable limits
        """
        limits_to_check = self.limits
        if limit_name:
            limits_to_check = [l for l in self.limits if l.name == limit_name]

        # Check all limits first
        for limit in limits_to_check:
            scope_key = self._get_scope_key(limit, model, card_id, user_id)
            bucket = self._get_bucket(limit, scope_key)

            if bucket.get_available_tokens() < tokens:
                stats = self._stats[limit.name]
                stats.total_requests += 1
                stats.blocked_requests += 1

                wait_time = bucket.time_until_available(tokens)
                if self.on_limit_exceeded:
                    self.on_limit_exceeded(limit.name, wait_time)

                self._log_event("blocked", limit.name, {
                    "tokens_requested": tokens,
                    "tokens_available": bucket.get_available_tokens(),
                    "wait_time_seconds": wait_time,
                    "model": model,
                    "card_id": card_id,
                })

                return False

        # Acquire from all limits
        for limit in limits_to_check:
            scope_key = self._get_scope_key(limit, model, card_id, user_id)
            bucket = self._get_bucket(limit, scope_key)
            bucket.try_acquire(tokens)

            stats = self._stats[limit.name]
            stats.total_requests += 1
            stats.allowed_requests += 1
            stats.tokens_consumed += tokens

        return True

    def acquire(
        self,
        limit_name: Optional[str] = None,
        tokens: float = 1.0,
        timeout: float = 30.0,
        blocking: bool = True,
        model: Optional[str] = None,
        card_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Acquire tokens, optionally blocking.

        Args:
            limit_name: Specific limit to check (None = all limits)
            tokens: Number of tokens to acquire
            timeout: Maximum wait time in seconds
            blocking: If True, wait for tokens; if False, fail immediately
            model: Model name for per-model limits
            card_id: Card ID for per-card limits
            user_id: User ID for per-user limits

        Returns:
            True if tokens acquired

        Raises:
            RateLimitExceededError: If blocking=False and limit exceeded
        """
        if not blocking:
            result = self.try_acquire(limit_name, tokens, model, card_id, user_id)
            if not result:
                # Find the limiting factor
                for limit in self.limits:
                    if limit_name and limit.name != limit_name:
                        continue
                    scope_key = self._get_scope_key(limit, model, card_id, user_id)
                    bucket = self._get_bucket(limit, scope_key)
                    if bucket.get_available_tokens() < tokens:
                        raise RateLimitExceededError(
                            limit.name,
                            tokens,
                            bucket.get_available_tokens(),
                            bucket.time_until_available(tokens),
                        )
            return result

        # Blocking mode - wait for all limits
        start_time = time.monotonic()
        deadline = start_time + timeout

        limits_to_check = self.limits
        if limit_name:
            limits_to_check = [l for l in self.limits if l.name == limit_name]

        for limit in limits_to_check:
            scope_key = self._get_scope_key(limit, model, card_id, user_id)
            bucket = self._get_bucket(limit, scope_key)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            if not bucket.acquire_blocking(tokens, remaining):
                return False

            stats = self._stats[limit.name]
            stats.total_requests += 1
            stats.allowed_requests += 1
            stats.tokens_consumed += tokens

        total_wait = (time.monotonic() - start_time) * 1000
        if total_wait > 0:
            for limit in limits_to_check:
                self._stats[limit.name].total_wait_time_ms += total_wait / len(limits_to_check)

        return True

    async def acquire_async(
        self,
        limit_name: Optional[str] = None,
        tokens: float = 1.0,
        timeout: float = 30.0,
        model: Optional[str] = None,
        card_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Acquire tokens asynchronously.

        Args:
            limit_name: Specific limit to check (None = all limits)
            tokens: Number of tokens to acquire
            timeout: Maximum wait time in seconds
            model: Model name for per-model limits
            card_id: Card ID for per-card limits
            user_id: User ID for per-user limits

        Returns:
            True if tokens acquired
        """
        start_time = time.monotonic()
        deadline = start_time + timeout

        limits_to_check = self.limits
        if limit_name:
            limits_to_check = [l for l in self.limits if l.name == limit_name]

        for limit in limits_to_check:
            scope_key = self._get_scope_key(limit, model, card_id, user_id)
            bucket = self._get_bucket(limit, scope_key)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False

            if not await bucket.acquire_async(tokens, remaining):
                return False

            stats = self._stats[limit.name]
            stats.total_requests += 1
            stats.allowed_requests += 1
            stats.tokens_consumed += tokens

        return True

    def get_stats(self, limit_name: Optional[str] = None) -> Dict[str, RateLimitStats]:
        """Get statistics for limits."""
        if limit_name:
            return {limit_name: self._stats.get(limit_name, RateLimitStats())}
        return dict(self._stats)

    def get_bucket_status(
        self,
        limit_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get current bucket status."""
        result = {}

        for limit in self.limits:
            if limit_name and limit.name != limit_name:
                continue

            if limit.scope == LimitScope.GLOBAL:
                bucket = self._global_buckets.get(limit.name)
                if bucket:
                    result[limit.name] = {
                        "scope": "global",
                        "buckets": {"global": bucket.to_dict()},
                    }
            else:
                buckets = self._scoped_buckets.get(limit.name, {})
                result[limit.name] = {
                    "scope": limit.scope.value,
                    "buckets": {k: b.to_dict() for k, b in buckets.items()},
                }

        return result

    def reset_limit(self, limit_name: str) -> None:
        """Reset a limit's buckets to full."""
        for limit in self.limits:
            if limit.name == limit_name:
                if limit.scope == LimitScope.GLOBAL:
                    if limit_name in self._global_buckets:
                        self._global_buckets[limit_name] = TokenBucket(config=limit)
                else:
                    self._scoped_buckets[limit_name] = {}
                self._stats[limit_name] = RateLimitStats()
                break


# Convenience functions
def create_default_limiter(
    ledger: Optional[EventLogger] = None,
) -> RateLimiter:
    """Create a rate limiter with default limits."""
    return RateLimiter(limits=RateLimiter.DEFAULT_LIMITS, ledger=ledger)


def create_claude_limiter(
    ledger: Optional[EventLogger] = None,
) -> RateLimiter:
    """Create a rate limiter optimized for Claude API."""
    return RateLimiter(limits=RateLimiter.CLAUDE_LIMITS, ledger=ledger)


def create_per_card_limiter(
    requests_per_second: float = 2.0,
    burst_size: float = 10.0,
    ledger: Optional[EventLogger] = None,
) -> RateLimiter:
    """Create a per-card rate limiter."""
    limits = [
        RateLimitConfig(
            name="per_card_requests",
            tokens_per_second=requests_per_second,
            bucket_size=burst_size,
            scope=LimitScope.PER_CARD,
        ),
    ]
    return RateLimiter(limits=limits, ledger=ledger)
