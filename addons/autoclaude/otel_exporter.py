#!/usr/bin/env python3
"""
OpenTelemetry GenAI Exporter - Standard LLM Observability

Inspired by:
- OpenTelemetry GenAI Semantic Conventions (v1.37+)
- Datadog/Arize LLM Observability patterns
- Quranic Hisab (Accountability): Complete traceable records

Features:
- GenAI semantic conventions compliance
- Span creation for LLM calls
- Token usage metrics
- OTLP export support
- Trace context propagation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import hashlib
import threading
import time
import random

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/otel_exporter.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SpanKind(Enum):
    """OpenTelemetry span kinds."""
    CLIENT = "client"
    SERVER = "server"
    INTERNAL = "internal"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(Enum):
    """Span status codes."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class GenAIOperationType(Enum):
    """GenAI operation types per semantic conventions."""
    CHAT = "chat"
    TEXT_COMPLETION = "text_completion"
    EMBEDDINGS = "embeddings"
    IMAGE_GENERATION = "image_generation"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    AGENT = "agent"
    TOOL_CALL = "tool_call"


# OpenTelemetry GenAI Semantic Convention attribute names
class GenAIAttributes:
    """Standard GenAI semantic convention attributes."""
    # Request attributes
    OPERATION_NAME = "gen_ai.operation.name"
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    REQUEST_TOP_P = "gen_ai.request.top_p"
    REQUEST_TOP_K = "gen_ai.request.top_k"
    REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
    REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
    REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"

    # Response attributes
    RESPONSE_ID = "gen_ai.response.id"
    RESPONSE_MODEL = "gen_ai.response.model"
    RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

    # Usage attributes
    USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"

    # System attributes
    SYSTEM = "gen_ai.system"  # e.g., "openai", "anthropic"

    # Agent-specific
    AGENT_NAME = "gen_ai.agent.name"
    AGENT_DESCRIPTION = "gen_ai.agent.description"
    TOOL_NAME = "gen_ai.tool.name"
    TOOL_CALL_ID = "gen_ai.tool.call_id"

    # Error attributes
    ERROR_TYPE = "error.type"
    ERROR_MESSAGE = "error.message"


@dataclass
class SpanContext:
    """Trace context for span correlation."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    trace_flags: int = 1  # sampled
    trace_state: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_flags": self.trace_flags
        }


@dataclass
class SpanEvent:
    """Event within a span."""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """OpenTelemetry-compatible span."""
    name: str
    context: SpanContext
    kind: SpanKind
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    status_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanContext] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append(SpanEvent(
            name=name,
            timestamp=_now_utc(),
            attributes=attributes or {}
        ))

    def set_status(self, status: SpanStatus, message: Optional[str] = None) -> None:
        """Set span status."""
        self.status = status
        self.status_message = message

    def end(self, end_time: Optional[datetime] = None) -> None:
        """End the span."""
        self.end_time = end_time or _now_utc()

    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_otlp(self) -> Dict[str, Any]:
        """Convert to OTLP format."""
        return {
            "traceId": self.context.trace_id,
            "spanId": self.context.span_id,
            "parentSpanId": self.context.parent_span_id,
            "name": self.name,
            "kind": self.kind.value.upper(),
            "startTimeUnixNano": int(self.start_time.timestamp() * 1e9),
            "endTimeUnixNano": int(self.end_time.timestamp() * 1e9) if self.end_time else 0,
            "attributes": [
                {"key": k, "value": self._format_value(v)}
                for k, v in self.attributes.items()
            ],
            "status": {
                "code": self.status.value.upper(),
                "message": self.status_message
            },
            "events": [
                {
                    "name": e.name,
                    "timeUnixNano": int(e.timestamp.timestamp() * 1e9),
                    "attributes": [
                        {"key": k, "value": self._format_value(v)}
                        for k, v in e.attributes.items()
                    ]
                }
                for e in self.events
            ]
        }

    def _format_value(self, value: Any) -> Dict[str, Any]:
        """Format value for OTLP."""
        if isinstance(value, bool):
            return {"boolValue": value}
        elif isinstance(value, int):
            return {"intValue": str(value)}
        elif isinstance(value, float):
            return {"doubleValue": value}
        elif isinstance(value, list):
            return {"arrayValue": {"values": [self._format_value(v) for v in value]}}
        else:
            return {"stringValue": str(value)}


@dataclass
class OTelConfig:
    """Configuration for OpenTelemetry exporter."""
    service_name: str = "autoclaude"
    service_version: str = "1.2.0"
    otlp_endpoint: Optional[str] = None  # e.g., "http://localhost:4318"
    export_interval_seconds: float = 30.0
    batch_size: int = 100
    enable_console_export: bool = False
    sampling_rate: float = 1.0  # 0.0 to 1.0


class OTelExporter:
    """
    OpenTelemetry-compatible exporter for LLM observability.

    Hisab (Accountability) Principle: Complete traceable records
    - Every LLM call is traced
    - Token usage is tracked
    - Errors are recorded with context
    """

    def __init__(
        self,
        config: Optional[OTelConfig] = None,
        ledger_path: Optional[str] = None
    ):
        self._config = config or OTelConfig()
        self._spans: List[Span] = []
        self._active_spans: Dict[str, Span] = {}
        self._lock = threading.Lock()
        self._export_callbacks: List[Callable[[List[Span]], None]] = []

        # Context propagation
        self._context_var = threading.local()

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

    def _generate_trace_id(self) -> str:
        """Generate 32-character trace ID."""
        return hashlib.sha256(
            f"{time.time_ns()}:{random.random()}".encode()
        ).hexdigest()[:32]

    def _generate_span_id(self) -> str:
        """Generate 16-character span ID."""
        return hashlib.sha256(
            f"{time.time_ns()}:{random.random()}".encode()
        ).hexdigest()[:16]

    def _should_sample(self) -> bool:
        """Determine if this trace should be sampled."""
        return random.random() < self._config.sampling_rate

    def get_current_span(self) -> Optional[Span]:
        """Get the currently active span."""
        return getattr(self._context_var, 'current_span', None)

    def _set_current_span(self, span: Optional[Span]) -> None:
        """Set the current span in context."""
        self._context_var.current_span = span

    @contextmanager
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.CLIENT,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[List[SpanContext]] = None
    ):
        """Start a new span with context manager."""
        if not self._should_sample():
            yield None
            return

        # Get parent context
        parent_span = self.get_current_span()
        if parent_span:
            trace_id = parent_span.context.trace_id
            parent_span_id = parent_span.context.span_id
        else:
            trace_id = self._generate_trace_id()
            parent_span_id = None

        context = SpanContext(
            trace_id=trace_id,
            span_id=self._generate_span_id(),
            parent_span_id=parent_span_id
        )

        span = Span(
            name=name,
            context=context,
            kind=kind,
            start_time=_now_utc(),
            attributes=attributes or {},
            links=links or []
        )

        # Add service attributes
        span.set_attribute("service.name", self._config.service_name)
        span.set_attribute("service.version", self._config.service_version)

        with self._lock:
            self._active_spans[context.span_id] = span

        self._set_current_span(span)

        try:
            yield span
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            span.set_attribute(GenAIAttributes.ERROR_TYPE, type(e).__name__)
            span.set_attribute(GenAIAttributes.ERROR_MESSAGE, str(e))
            raise
        finally:
            span.end()
            self._set_current_span(parent_span)

            with self._lock:
                self._active_spans.pop(context.span_id, None)
                self._spans.append(span)

            # Auto-export if batch size reached
            if len(self._spans) >= self._config.batch_size:
                self._export_batch()

    def create_llm_span(
        self,
        operation: GenAIOperationType,
        model: str,
        system: str = "anthropic",
        **request_params
    ):
        """
        Create a span for an LLM operation with GenAI semantic conventions.

        Args:
            operation: Type of GenAI operation
            model: Model name (e.g., "claude-3-opus")
            system: Provider name (e.g., "anthropic", "openai")
            **request_params: Additional request parameters
        """
        span_name = f"{operation.value} {model}"

        attributes = {
            GenAIAttributes.OPERATION_NAME: operation.value,
            GenAIAttributes.REQUEST_MODEL: model,
            GenAIAttributes.SYSTEM: system
        }

        # Add request parameters
        if "max_tokens" in request_params:
            attributes[GenAIAttributes.REQUEST_MAX_TOKENS] = request_params["max_tokens"]
        if "temperature" in request_params:
            attributes[GenAIAttributes.REQUEST_TEMPERATURE] = request_params["temperature"]
        if "top_p" in request_params:
            attributes[GenAIAttributes.REQUEST_TOP_P] = request_params["top_p"]
        if "top_k" in request_params:
            attributes[GenAIAttributes.REQUEST_TOP_K] = request_params["top_k"]

        return self.start_span(span_name, SpanKind.CLIENT, attributes)

    def record_llm_response(
        self,
        span: Span,
        response_id: str,
        response_model: str,
        input_tokens: int,
        output_tokens: int,
        finish_reason: str = "stop"
    ) -> None:
        """Record LLM response details on a span."""
        if not span:
            return

        span.set_attribute(GenAIAttributes.RESPONSE_ID, response_id)
        span.set_attribute(GenAIAttributes.RESPONSE_MODEL, response_model)
        span.set_attribute(GenAIAttributes.RESPONSE_FINISH_REASONS, [finish_reason])
        span.set_attribute(GenAIAttributes.USAGE_INPUT_TOKENS, input_tokens)
        span.set_attribute(GenAIAttributes.USAGE_OUTPUT_TOKENS, output_tokens)
        span.set_attribute(GenAIAttributes.USAGE_TOTAL_TOKENS, input_tokens + output_tokens)

        span.set_status(SpanStatus.OK)

    def create_agent_span(
        self,
        agent_name: str,
        description: Optional[str] = None
    ):
        """Create a span for an agent operation."""
        attributes = {
            GenAIAttributes.OPERATION_NAME: GenAIOperationType.AGENT.value,
            GenAIAttributes.AGENT_NAME: agent_name
        }
        if description:
            attributes[GenAIAttributes.AGENT_DESCRIPTION] = description

        return self.start_span(f"agent {agent_name}", SpanKind.INTERNAL, attributes)

    def create_tool_span(
        self,
        tool_name: str,
        call_id: Optional[str] = None
    ):
        """Create a span for a tool call."""
        attributes = {
            GenAIAttributes.OPERATION_NAME: GenAIOperationType.TOOL_CALL.value,
            GenAIAttributes.TOOL_NAME: tool_name
        }
        if call_id:
            attributes[GenAIAttributes.TOOL_CALL_ID] = call_id

        return self.start_span(f"tool {tool_name}", SpanKind.INTERNAL, attributes)

    def add_export_callback(self, callback: Callable[[List[Span]], None]) -> None:
        """Add a callback for when spans are exported."""
        self._export_callbacks.append(callback)

    def _export_batch(self) -> None:
        """Export accumulated spans."""
        with self._lock:
            to_export = self._spans.copy()
            self._spans.clear()

        if not to_export:
            return

        # Console export
        if self._config.enable_console_export:
            for span in to_export:
                print(json.dumps(span.to_otlp(), indent=2))

        # Callbacks
        for callback in self._export_callbacks:
            try:
                callback(to_export)
            except Exception:
                pass  # Don't fail on callback errors

        # Log to ledger
        if self._logger:
            for span in to_export:
                self._logger.log_event(
                    event_type="OTEL_SPAN",
                    card_id="autoclaude",
                    details={
                        "trace_id": span.context.trace_id,
                        "span_id": span.context.span_id,
                        "name": span.name,
                        "duration_ms": span.duration_ms(),
                        "status": span.status.value
                    }
                )

    def export_otlp_json(self) -> Dict[str, Any]:
        """Export all spans in OTLP JSON format."""
        with self._lock:
            spans = self._spans.copy()

        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self._config.service_name}},
                            {"key": "service.version", "value": {"stringValue": self._config.service_version}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": "autoclaude.otel_exporter",
                                "version": "1.0.0"
                            },
                            "spans": [span.to_otlp() for span in spans]
                        }
                    ]
                }
            ]
        }

    def flush(self) -> None:
        """Force export of all pending spans."""
        self._export_batch()

    def get_stats(self) -> Dict[str, Any]:
        """Get exporter statistics."""
        with self._lock:
            return {
                "pending_spans": len(self._spans),
                "active_spans": len(self._active_spans),
                "service_name": self._config.service_name,
                "sampling_rate": self._config.sampling_rate,
                "batch_size": self._config.batch_size
            }


# Convenience functions for quick instrumentation
_default_exporter: Optional[OTelExporter] = None


def get_exporter() -> OTelExporter:
    """Get or create default exporter."""
    global _default_exporter
    if _default_exporter is None:
        _default_exporter = OTelExporter()
    return _default_exporter


def trace_llm_call(
    operation: GenAIOperationType,
    model: str,
    system: str = "anthropic"
):
    """Decorator to trace LLM calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            exporter = get_exporter()
            with exporter.create_llm_span(operation, model, system) as span:
                result = func(*args, **kwargs)
                # Try to extract token info from result
                if isinstance(result, dict):
                    if "usage" in result:
                        usage = result["usage"]
                        exporter.record_llm_response(
                            span,
                            response_id=result.get("id", ""),
                            response_model=result.get("model", model),
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0)
                        )
                return result
        return wrapper
    return decorator


# Convenience exports
__all__ = [
    "OTelExporter",
    "OTelConfig",
    "Span",
    "SpanContext",
    "SpanEvent",
    "SpanKind",
    "SpanStatus",
    "GenAIOperationType",
    "GenAIAttributes",
    "get_exporter",
    "trace_llm_call"
]
