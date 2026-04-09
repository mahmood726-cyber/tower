#!/usr/bin/env python3
"""
Metrics Exporter for Observability

Provides metrics export with:
- Prometheus-compatible metrics endpoint
- StatsD/Datadog integration
- OpenTelemetry spans support
- Built-in metric collectors
- Custom metric registration
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict

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


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"         # Monotonically increasing
    GAUGE = "gauge"             # Can go up or down
    HISTOGRAM = "histogram"     # Distribution of values
    SUMMARY = "summary"         # Statistical summary


@dataclass
class MetricLabel:
    """A label for a metric."""
    name: str
    value: str


@dataclass
class MetricValue:
    """A metric value with labels."""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HistogramBucket:
    """A histogram bucket."""
    le: float  # Less than or equal
    count: int = 0


@dataclass
class Metric:
    """A metric definition."""

    name: str
    metric_type: MetricType
    help_text: str = ""
    labels: List[str] = field(default_factory=list)
    values: Dict[str, MetricValue] = field(default_factory=dict)
    buckets: List[HistogramBucket] = field(default_factory=list)
    sum_value: float = 0.0
    count_value: int = 0

    def get_label_key(self, labels: Dict[str, str]) -> str:
        """Generate unique key for label combination."""
        if not labels:
            return "__default__"
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def to_prometheus(self) -> str:
        """Export in Prometheus format."""
        lines = []

        # Help and type
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} {self.metric_type.value}")

        if self.metric_type == MetricType.HISTOGRAM:
            # Export buckets
            for bucket in self.buckets:
                label_str = f'le="{bucket.le}"'
                lines.append(f"{self.name}_bucket{{{label_str}}} {bucket.count}")

            lines.append(f"{self.name}_sum {self.sum_value}")
            lines.append(f"{self.name}_count {self.count_value}")

        else:
            # Export values
            for key, mv in self.values.items():
                if mv.labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in mv.labels.items())
                    lines.append(f"{self.name}{{{label_str}}} {mv.value}")
                else:
                    lines.append(f"{self.name} {mv.value}")

        return "\n".join(lines)


class MetricsRegistry:
    """Registry for metrics."""

    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        metric_type: MetricType,
        help_text: str = "",
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Metric:
        """Register a new metric."""
        with self._lock:
            if name in self.metrics:
                return self.metrics[name]

            histogram_buckets = []
            if metric_type == MetricType.HISTOGRAM and buckets:
                histogram_buckets = [HistogramBucket(le=b) for b in sorted(buckets)]
                histogram_buckets.append(HistogramBucket(le=float("inf")))

            metric = Metric(
                name=name,
                metric_type=metric_type,
                help_text=help_text,
                labels=labels or [],
                buckets=histogram_buckets,
            )

            self.metrics[name] = metric
            return metric

    def get(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        return self.metrics.get(name)

    def inc(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter."""
        with self._lock:
            metric = self.metrics.get(name)
            if not metric or metric.metric_type != MetricType.COUNTER:
                return

            key = metric.get_label_key(labels or {})
            if key not in metric.values:
                metric.values[key] = MetricValue(value=0.0, labels=labels or {})

            metric.values[key].value += value
            metric.values[key].timestamp = time.time()

    def set(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge value."""
        with self._lock:
            metric = self.metrics.get(name)
            if not metric or metric.metric_type != MetricType.GAUGE:
                return

            key = metric.get_label_key(labels or {})
            metric.values[key] = MetricValue(value=value, labels=labels or {})

    def observe(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Observe a histogram value."""
        with self._lock:
            metric = self.metrics.get(name)
            if not metric or metric.metric_type != MetricType.HISTOGRAM:
                return

            # Update buckets
            for bucket in metric.buckets:
                if value <= bucket.le:
                    bucket.count += 1

            metric.sum_value += value
            metric.count_value += 1

    def to_prometheus(self) -> str:
        """Export all metrics in Prometheus format."""
        with self._lock:
            lines = []
            for metric in self.metrics.values():
                lines.append(metric.to_prometheus())
            return "\n\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics endpoint."""

    registry: MetricsRegistry = None

    def do_GET(self):
        if self.path == "/metrics":
            content = self.registry.to_prometheus()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging


class MetricsExporter:
    """
    Exports metrics for observability.

    Features:
    - Prometheus-compatible /metrics endpoint
    - StatsD UDP export
    - Custom metric collectors
    - Built-in LLM agent metrics
    """

    # Default histogram buckets for latency (in milliseconds)
    LATENCY_BUCKETS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

    # Default histogram buckets for tokens
    TOKEN_BUCKETS = [100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]

    def __init__(
        self,
        namespace: str = "tower",
        enable_default_metrics: bool = True,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize metrics exporter.

        Args:
            namespace: Metric namespace prefix
            enable_default_metrics: Register default LLM metrics
            ledger: Optional EventLogger
        """
        self.namespace = namespace
        self.registry = MetricsRegistry()
        self.ledger = ledger

        self._http_server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._statsd_socket = None
        self._collectors: List[Callable[[], None]] = []

        if enable_default_metrics:
            self._register_default_metrics()

    def _register_default_metrics(self) -> None:
        """Register default LLM agent metrics."""
        # Request metrics
        self.registry.register(
            f"{self.namespace}_llm_requests_total",
            MetricType.COUNTER,
            "Total LLM API requests",
            labels=["model", "status"],
        )

        self.registry.register(
            f"{self.namespace}_llm_request_duration_ms",
            MetricType.HISTOGRAM,
            "LLM request duration in milliseconds",
            labels=["model"],
            buckets=self.LATENCY_BUCKETS,
        )

        # Token metrics
        self.registry.register(
            f"{self.namespace}_llm_tokens_total",
            MetricType.COUNTER,
            "Total tokens used",
            labels=["model", "type"],  # type: input/output
        )

        self.registry.register(
            f"{self.namespace}_llm_tokens_per_request",
            MetricType.HISTOGRAM,
            "Tokens per request",
            labels=["model"],
            buckets=self.TOKEN_BUCKETS,
        )

        # Cost metrics
        self.registry.register(
            f"{self.namespace}_llm_cost_total",
            MetricType.COUNTER,
            "Total cost in dollars",
            labels=["model"],
        )

        # Error metrics
        self.registry.register(
            f"{self.namespace}_llm_errors_total",
            MetricType.COUNTER,
            "Total errors",
            labels=["model", "error_type"],
        )

        # Circuit breaker metrics
        self.registry.register(
            f"{self.namespace}_circuit_breaker_state",
            MetricType.GAUGE,
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
            labels=["name"],
        )

        self.registry.register(
            f"{self.namespace}_circuit_breaker_failures_total",
            MetricType.COUNTER,
            "Circuit breaker failure count",
            labels=["name"],
        )

        # Retry metrics
        self.registry.register(
            f"{self.namespace}_retry_attempts_total",
            MetricType.COUNTER,
            "Total retry attempts",
            labels=["operation"],
        )

        # Session metrics
        self.registry.register(
            f"{self.namespace}_sessions_active",
            MetricType.GAUGE,
            "Active sessions",
        )

        self.registry.register(
            f"{self.namespace}_session_messages_total",
            MetricType.COUNTER,
            "Total session messages",
            labels=["role"],
        )

        # Checkpoint metrics
        self.registry.register(
            f"{self.namespace}_checkpoints_pending",
            MetricType.GAUGE,
            "Pending checkpoints awaiting approval",
        )

        self.registry.register(
            f"{self.namespace}_checkpoints_total",
            MetricType.COUNTER,
            "Total checkpoints created",
            labels=["status"],
        )

        # Guardrail metrics
        self.registry.register(
            f"{self.namespace}_guardrail_violations_total",
            MetricType.COUNTER,
            "Total guardrail violations",
            labels=["type", "action"],
        )

        # Rate limit metrics
        self.registry.register(
            f"{self.namespace}_rate_limit_blocked_total",
            MetricType.COUNTER,
            "Requests blocked by rate limiter",
            labels=["limit"],
        )

    def record_llm_request(
        self,
        model: str,
        duration_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool = True,
        error_type: Optional[str] = None,
    ) -> None:
        """Record metrics for an LLM request."""
        status = "success" if success else "error"

        # Request count
        self.registry.inc(
            f"{self.namespace}_llm_requests_total",
            labels={"model": model, "status": status},
        )

        # Duration
        self.registry.observe(
            f"{self.namespace}_llm_request_duration_ms",
            duration_ms,
            labels={"model": model},
        )

        # Tokens
        self.registry.inc(
            f"{self.namespace}_llm_tokens_total",
            input_tokens,
            labels={"model": model, "type": "input"},
        )
        self.registry.inc(
            f"{self.namespace}_llm_tokens_total",
            output_tokens,
            labels={"model": model, "type": "output"},
        )

        total_tokens = input_tokens + output_tokens
        self.registry.observe(
            f"{self.namespace}_llm_tokens_per_request",
            total_tokens,
            labels={"model": model},
        )

        # Cost
        self.registry.inc(
            f"{self.namespace}_llm_cost_total",
            cost,
            labels={"model": model},
        )

        # Errors
        if not success and error_type:
            self.registry.inc(
                f"{self.namespace}_llm_errors_total",
                labels={"model": model, "error_type": error_type},
            )

    def record_circuit_breaker(
        self,
        name: str,
        state: int,  # 0=closed, 1=open, 2=half_open
        failure: bool = False,
    ) -> None:
        """Record circuit breaker metrics."""
        self.registry.set(
            f"{self.namespace}_circuit_breaker_state",
            float(state),
            labels={"name": name},
        )

        if failure:
            self.registry.inc(
                f"{self.namespace}_circuit_breaker_failures_total",
                labels={"name": name},
            )

    def record_retry(self, operation: str, attempts: int = 1) -> None:
        """Record retry metrics."""
        self.registry.inc(
            f"{self.namespace}_retry_attempts_total",
            float(attempts),
            labels={"operation": operation},
        )

    def record_guardrail_violation(
        self,
        violation_type: str,
        action: str,
    ) -> None:
        """Record guardrail violation."""
        self.registry.inc(
            f"{self.namespace}_guardrail_violations_total",
            labels={"type": violation_type, "action": action},
        )

    def record_checkpoint(self, status: str) -> None:
        """Record checkpoint metrics."""
        self.registry.inc(
            f"{self.namespace}_checkpoints_total",
            labels={"status": status},
        )

    def set_active_sessions(self, count: int) -> None:
        """Set active session count."""
        self.registry.set(f"{self.namespace}_sessions_active", float(count))

    def set_pending_checkpoints(self, count: int) -> None:
        """Set pending checkpoint count."""
        self.registry.set(f"{self.namespace}_checkpoints_pending", float(count))

    def record_session_message(self, role: str) -> None:
        """Record session message."""
        self.registry.inc(
            f"{self.namespace}_session_messages_total",
            labels={"role": role},
        )

    def record_rate_limit_blocked(self, limit: str) -> None:
        """Record rate limit block."""
        self.registry.inc(
            f"{self.namespace}_rate_limit_blocked_total",
            labels={"limit": limit},
        )

    def add_collector(self, collector: Callable[[], None]) -> None:
        """Add a custom metric collector."""
        self._collectors.append(collector)

    def collect(self) -> None:
        """Run all collectors."""
        for collector in self._collectors:
            try:
                collector()
            except Exception:
                pass

    def start_http_server(self, port: int = 9090, host: str = "127.0.0.1") -> None:
        """Start Prometheus metrics HTTP server."""
        if self._http_server:
            return

        # Set registry on handler class
        MetricsHandler.registry = self.registry

        self._http_server = HTTPServer((host, port), MetricsHandler)

        def serve():
            self._http_server.serve_forever()

        self._server_thread = threading.Thread(target=serve, daemon=True)
        self._server_thread.start()

        if self.ledger:
            self.ledger.log(
                event_type="metrics.server_started",
                card_id=None,
                actor="metrics_exporter",
                data={"host": host, "port": port},
            )

    def stop_http_server(self) -> None:
        """Stop the HTTP server."""
        if self._http_server:
            self._http_server.shutdown()
            self._http_server = None
            self._server_thread = None

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        self.collect()
        return self.registry.to_prometheus()

    def export_json(self) -> Dict[str, Any]:
        """Export metrics as JSON."""
        self.collect()

        result = {}
        for name, metric in self.registry.metrics.items():
            if metric.metric_type == MetricType.HISTOGRAM:
                result[name] = {
                    "type": "histogram",
                    "buckets": {str(b.le): b.count for b in metric.buckets},
                    "sum": metric.sum_value,
                    "count": metric.count_value,
                }
            else:
                values = {}
                for key, mv in metric.values.items():
                    if mv.labels:
                        values[key] = {"value": mv.value, "labels": mv.labels}
                    else:
                        values["_"] = mv.value

                result[name] = {
                    "type": metric.metric_type.value,
                    "values": values,
                }

        return result

    def send_to_statsd(
        self,
        host: str = "127.0.0.1",
        port: int = 8125,
        prefix: Optional[str] = None,
    ) -> None:
        """Send metrics to StatsD/Datadog."""
        import socket

        prefix = prefix or self.namespace

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            for name, metric in self.registry.metrics.items():
                metric_name = f"{prefix}.{name}"

                if metric.metric_type in (MetricType.COUNTER, MetricType.GAUGE):
                    for key, mv in metric.values.items():
                        # Format: metric_name:value|type|#tags
                        stat_type = "c" if metric.metric_type == MetricType.COUNTER else "g"
                        tags = ",".join(f"{k}:{v}" for k, v in mv.labels.items())
                        message = f"{metric_name}:{mv.value}|{stat_type}"
                        if tags:
                            message += f"|#{tags}"

                        sock.sendto(message.encode(), (host, port))

            sock.close()

        except Exception as e:
            if self.ledger:
                self.ledger.log(
                    event_type="metrics.statsd_error",
                    card_id=None,
                    actor="metrics_exporter",
                    data={"error": str(e)},
                )


# Convenience functions
def create_metrics_exporter(
    namespace: str = "tower",
    ledger: Optional[EventLogger] = None,
) -> MetricsExporter:
    """Create a metrics exporter with default configuration."""
    return MetricsExporter(namespace=namespace, ledger=ledger)


def get_global_exporter() -> MetricsExporter:
    """Get or create global metrics exporter."""
    global _global_exporter
    if "_global_exporter" not in globals():
        _global_exporter = MetricsExporter()
    return _global_exporter
