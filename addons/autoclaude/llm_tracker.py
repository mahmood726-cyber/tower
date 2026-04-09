#!/usr/bin/env python3
"""
LLM Token and Cost Tracking

Tracks token usage and costs across LLM API calls with:
- Per-call tracking with full context
- Aggregation by model, card, session
- Budget enforcement with alerts
- Cost projections and reporting
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

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


# Model pricing (USD per 1M tokens) - updated Jan 2025
MODEL_PRICING = {
    # Claude models
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    # GPT models
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Default fallback
    "default": {"input": 5.00, "output": 15.00},
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LLMCall:
    """Record of a single LLM API call."""

    call_id: str
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    card_id: Optional[str] = None
    session_id: Optional[str] = None
    prompt_hash: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostReport:
    """Aggregated cost report."""

    period_start: str
    period_end: str
    total_calls: int
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    by_model: Dict[str, Dict[str, Any]]
    by_card: Dict[str, Dict[str, Any]]
    by_session: Dict[str, Dict[str, Any]]
    budget_usd: Optional[float] = None
    budget_remaining_usd: Optional[float] = None
    budget_utilization_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BudgetExceededError(Exception):
    """Raised when LLM budget is exceeded."""
    pass


class LLMTracker:
    """
    Tracks LLM API token usage and costs.

    Features:
    - Per-call logging with full context
    - Cost calculation based on model pricing
    - Budget enforcement with configurable limits
    - Aggregation and reporting
    - Integration with Tower event ledger
    """

    def __init__(
        self,
        tracker_path: Optional[str] = None,
        budget_daily_usd: Optional[float] = None,
        budget_monthly_usd: Optional[float] = None,
        budget_per_card_usd: Optional[float] = None,
        on_budget_warning: Optional[Callable[[float, float], None]] = None,
        warning_threshold_pct: float = 80.0,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize LLM tracker.

        Args:
            tracker_path: Path to tracker JSONL file (default: control/llm_tracker.jsonl)
            budget_daily_usd: Daily budget limit in USD
            budget_monthly_usd: Monthly budget limit in USD
            budget_per_card_usd: Per-card budget limit in USD
            on_budget_warning: Callback when budget threshold reached
            warning_threshold_pct: Percentage of budget that triggers warning
            ledger: Optional EventLogger for integrated logging
        """
        if tracker_path:
            self.tracker_path = Path(tracker_path)
        else:
            self.tracker_path = CONTROL_DIR / "llm_tracker.jsonl"

        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)

        self.budget_daily_usd = budget_daily_usd
        self.budget_monthly_usd = budget_monthly_usd
        self.budget_per_card_usd = budget_per_card_usd
        self.on_budget_warning = on_budget_warning
        self.warning_threshold_pct = warning_threshold_pct
        self.ledger = ledger

        self._call_counter = 0

    def _generate_call_id(self) -> str:
        """Generate unique call ID."""
        ts = _now_utc().strftime("%Y%m%d%H%M%S")
        self._call_counter += 1
        return f"llm_{ts}_{self._call_counter:04d}"

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for model."""
        # Try exact match
        if model in MODEL_PRICING:
            return MODEL_PRICING[model]

        # Try prefix match
        for model_prefix, pricing in MODEL_PRICING.items():
            if model.startswith(model_prefix):
                return pricing

        # Default pricing
        return MODEL_PRICING["default"]

    def _calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Calculate cost in USD."""
        pricing = self._get_pricing(model)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def _check_budget(
        self,
        card_id: Optional[str] = None,
        additional_cost: float = 0.0,
    ) -> None:
        """Check if budget allows the call."""
        now = _now_utc()

        # Check daily budget
        if self.budget_daily_usd is not None:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_report = self.get_report(since=today_start.isoformat())
            daily_total = daily_report.total_cost_usd + additional_cost

            if daily_total > self.budget_daily_usd:
                raise BudgetExceededError(
                    f"Daily budget exceeded: ${daily_total:.2f} > ${self.budget_daily_usd:.2f}"
                )

            if self.on_budget_warning:
                pct = (daily_total / self.budget_daily_usd) * 100
                if pct >= self.warning_threshold_pct:
                    self.on_budget_warning(daily_total, self.budget_daily_usd)

        # Check monthly budget
        if self.budget_monthly_usd is not None:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_report = self.get_report(since=month_start.isoformat())
            monthly_total = monthly_report.total_cost_usd + additional_cost

            if monthly_total > self.budget_monthly_usd:
                raise BudgetExceededError(
                    f"Monthly budget exceeded: ${monthly_total:.2f} > ${self.budget_monthly_usd:.2f}"
                )

        # Check per-card budget
        if self.budget_per_card_usd is not None and card_id:
            card_report = self.get_report(card_id=card_id)
            card_total = card_report.total_cost_usd + additional_cost

            if card_total > self.budget_per_card_usd:
                raise BudgetExceededError(
                    f"Card budget exceeded for {card_id}: ${card_total:.2f} > ${self.budget_per_card_usd:.2f}"
                )

    def log_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        card_id: Optional[str] = None,
        session_id: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        check_budget: bool = True,
    ) -> LLMCall:
        """
        Log an LLM API call.

        Args:
            model: Model identifier (e.g., "claude-3-sonnet")
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            latency_ms: Call latency in milliseconds
            card_id: Associated card ID
            session_id: Session identifier
            prompt_hash: Hash of the prompt template used
            success: Whether the call succeeded
            error: Error message if failed
            metadata: Additional metadata
            check_budget: Whether to enforce budget limits

        Returns:
            LLMCall record

        Raises:
            BudgetExceededError: If budget would be exceeded
        """
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        # Check budget before logging
        if check_budget:
            self._check_budget(card_id=card_id, additional_cost=cost)

        call = LLMCall(
            call_id=self._generate_call_id(),
            timestamp=_now_utc().isoformat(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            card_id=card_id,
            session_id=session_id,
            prompt_hash=prompt_hash,
            success=success,
            error=error,
            metadata=metadata or {},
        )

        # Write to tracker file
        with open(self.tracker_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(call.to_dict(), separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # Log to event ledger if available
        if self.ledger:
            self.ledger.log(
                event_type="llm.call",
                card_id=card_id,
                actor="llm_tracker",
                data={
                    "call_id": call.call_id,
                    "model": model,
                    "tokens": call.total_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms,
                    "success": success,
                },
            )

        return call

    def _read_calls(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        card_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[LLMCall]:
        """Read calls matching filters."""
        if not self.tracker_path.exists():
            return []

        calls = []
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Apply filters
                if since and data.get("timestamp", "") < since:
                    continue
                if until and data.get("timestamp", "") > until:
                    continue
                if card_id and data.get("card_id") != card_id:
                    continue
                if session_id and data.get("session_id") != session_id:
                    continue
                if model and not data.get("model", "").startswith(model):
                    continue

                calls.append(LLMCall(**data))

        return calls

    def get_report(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        card_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> CostReport:
        """
        Generate aggregated cost report.

        Args:
            since: Start timestamp (ISO format)
            until: End timestamp (ISO format)
            card_id: Filter by card ID
            session_id: Filter by session ID

        Returns:
            CostReport with aggregated metrics
        """
        calls = self._read_calls(
            since=since,
            until=until,
            card_id=card_id,
            session_id=session_id,
        )

        # Aggregate
        by_model: Dict[str, Dict[str, Any]] = {}
        by_card: Dict[str, Dict[str, Any]] = {}
        by_session: Dict[str, Dict[str, Any]] = {}

        total_tokens = 0
        total_prompt = 0
        total_completion = 0
        total_cost = 0.0

        for call in calls:
            total_tokens += call.total_tokens
            total_prompt += call.prompt_tokens
            total_completion += call.completion_tokens
            total_cost += call.cost_usd

            # By model
            if call.model not in by_model:
                by_model[call.model] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_model[call.model]["calls"] += 1
            by_model[call.model]["tokens"] += call.total_tokens
            by_model[call.model]["cost_usd"] += call.cost_usd

            # By card
            if call.card_id:
                if call.card_id not in by_card:
                    by_card[call.card_id] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
                by_card[call.card_id]["calls"] += 1
                by_card[call.card_id]["tokens"] += call.total_tokens
                by_card[call.card_id]["cost_usd"] += call.cost_usd

            # By session
            if call.session_id:
                if call.session_id not in by_session:
                    by_session[call.session_id] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
                by_session[call.session_id]["calls"] += 1
                by_session[call.session_id]["tokens"] += call.total_tokens
                by_session[call.session_id]["cost_usd"] += call.cost_usd

        # Determine period
        now = _now_utc()
        period_start = since or (calls[0].timestamp if calls else now.isoformat())
        period_end = until or now.isoformat()

        # Budget info
        budget_usd = self.budget_daily_usd or self.budget_monthly_usd
        budget_remaining = None
        budget_utilization = None
        if budget_usd:
            budget_remaining = max(0, budget_usd - total_cost)
            budget_utilization = (total_cost / budget_usd) * 100 if budget_usd > 0 else 0

        return CostReport(
            period_start=period_start,
            period_end=period_end,
            total_calls=len(calls),
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_cost_usd=round(total_cost, 4),
            by_model=by_model,
            by_card=by_card,
            by_session=by_session,
            budget_usd=budget_usd,
            budget_remaining_usd=round(budget_remaining, 4) if budget_remaining else None,
            budget_utilization_pct=round(budget_utilization, 2) if budget_utilization else None,
        )

    def get_card_cost(self, card_id: str) -> float:
        """Get total cost for a card."""
        report = self.get_report(card_id=card_id)
        return report.total_cost_usd

    def get_daily_cost(self) -> float:
        """Get today's total cost."""
        now = _now_utc()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        report = self.get_report(since=today_start.isoformat())
        return report.total_cost_usd
