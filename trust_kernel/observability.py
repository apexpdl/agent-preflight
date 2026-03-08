"""
Preflight Observability Layer.

Structured logging, Prometheus-compatible metrics, and OpenTelemetry
span export for enterprise monitoring integration.

Integrates with Datadog, New Relic, Grafana, and any OTel-compatible
backend.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Structured Logger
# ---------------------------------------------------------------------------

class StructuredLogger:
    """JSON-structured logging for machine-parseable audit trails."""

    def __init__(
        self,
        name: str = "preflight",
        level: int = logging.INFO,
        max_entries: int = 100_000,
    ):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._entries: list[dict[str, Any]] = []
        self._max_entries = max_entries

    def log(
        self,
        event: str,
        level: str = "info",
        **kwargs: Any,
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "level": level,
            **kwargs,
        }

        # Rotate if at capacity
        if len(self._entries) >= self._max_entries:
            self._entries = self._entries[self._max_entries // 2:]

        self._entries.append(entry)

        log_fn = getattr(self._logger, level, self._logger.info)
        log_fn(json.dumps(entry, default=str))

        return entry

    def info(self, event: str, **kwargs: Any) -> dict[str, Any]:
        return self.log(event, "info", **kwargs)

    def warning(self, event: str, **kwargs: Any) -> dict[str, Any]:
        return self.log(event, "warning", **kwargs)

    def error(self, event: str, **kwargs: Any) -> dict[str, Any]:
        return self.log(event, "error", **kwargs)

    def critical(self, event: str, **kwargs: Any) -> dict[str, Any]:
        return self.log(event, "critical", **kwargs)

    def get_entries(
        self,
        level: Optional[str] = None,
        event: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        entries = self._entries
        if level:
            entries = [e for e in entries if e.get("level") == level]
        if event:
            entries = [e for e in entries if e.get("event") == event]
        return entries[-limit:]

    @property
    def entry_count(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Prometheus-Compatible Metrics
# ---------------------------------------------------------------------------

@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Prometheus-compatible metrics for Preflight operations.

    Exposes:
    - preflight_actions_total (counter)
    - preflight_actions_blocked_total (counter)
    - preflight_risk_score (histogram)
    - preflight_pipeline_duration_seconds (histogram)
    - preflight_simulation_runs_total (counter)
    - preflight_ledger_records_total (gauge)
    - preflight_consensus_pending (gauge)
    - preflight_budget_remaining (gauge)
    """

    def __init__(self):
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._labels: dict[str, dict[str, str]] = {}
        self._max_histogram_size = 10_000

    def inc_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = self._make_key(name, labels)
        self._counters[key] += value
        self._labels[key] = labels

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        key = self._make_key(name, labels)
        self._gauges[key] = value
        self._labels[key] = labels

    def observe_histogram(self, name: str, value: float, **labels: str) -> None:
        key = self._make_key(name, labels)
        hist = self._histograms[key]
        hist.append(value)
        if len(hist) > self._max_histogram_size:
            self._histograms[key] = hist[self._max_histogram_size // 2:]
        self._labels[key] = labels

    def record_action(
        self,
        verdict: str,
        risk_score: float,
        pipeline_ms: float,
        tool_name: str = "",
        agent_id: str = "",
    ) -> None:
        """Convenience: record a complete action evaluation."""
        self.inc_counter("preflight_actions_total", verdict=verdict)
        if verdict == "block":
            self.inc_counter("preflight_actions_blocked_total")
        self.observe_histogram(
            "preflight_risk_score", risk_score, tool=tool_name
        )
        self.observe_histogram(
            "preflight_pipeline_duration_seconds",
            pipeline_ms / 1000.0,
            tool=tool_name,
        )

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text exposition format."""
        lines = []
        lines.append("# Preflight Execution Firewall Metrics")
        lines.append("")

        for key, value in sorted(self._counters.items()):
            name, labels_str = self._parse_key(key)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{labels_str} {value}")

        for key, value in sorted(self._gauges.items()):
            name, labels_str = self._parse_key(key)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{labels_str} {value}")

        for key, values in sorted(self._histograms.items()):
            name, labels_str = self._parse_key(key)
            if values:
                lines.append(f"# TYPE {name} summary")
                sorted_vals = sorted(values)
                count = len(sorted_vals)
                total = sum(sorted_vals)
                lines.append(f"{name}_count{labels_str} {count}")
                lines.append(f"{name}_sum{labels_str} {total:.6f}")
                for q in (0.5, 0.9, 0.95, 0.99):
                    idx = min(int(count * q), count - 1)
                    lines.append(
                        f'{name}{{quantile="{q}"{labels_str.lstrip("{").rstrip("}") if labels_str else ""}}} {sorted_vals[idx]:.6f}'
                    )

        return "\n".join(lines) + "\n"

    def export_json(self) -> dict[str, Any]:
        """Export metrics as structured JSON."""
        result: dict[str, Any] = {
            "counters": {},
            "gauges": {},
            "histograms": {},
        }
        for key, value in self._counters.items():
            result["counters"][key] = value
        for key, value in self._gauges.items():
            result["gauges"][key] = value
        for key, values in self._histograms.items():
            if values:
                sorted_vals = sorted(values)
                count = len(sorted_vals)
                result["histograms"][key] = {
                    "count": count,
                    "sum": sum(sorted_vals),
                    "mean": sum(sorted_vals) / count,
                    "p50": sorted_vals[int(count * 0.5)],
                    "p95": sorted_vals[min(int(count * 0.95), count - 1)],
                    "p99": sorted_vals[min(int(count * 0.99), count - 1)],
                    "min": sorted_vals[0],
                    "max": sorted_vals[-1],
                }
        return result

    @staticmethod
    def _make_key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        label_parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_parts}}}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        if "{" in key:
            name = key[:key.index("{")]
            labels = key[key.index("{"):]
            return name, labels
        return key, ""


# ---------------------------------------------------------------------------
# OpenTelemetry Span Exporter (Interface)
# ---------------------------------------------------------------------------

@dataclass
class SpanRecord:
    """Lightweight span record for tracing integration."""
    trace_id: str
    span_id: str
    operation: str
    start_time: float
    end_time: float = 0.0
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


class SpanExporter:
    """Collects spans for OpenTelemetry-compatible export.

    In production, pipe these into the OTel SDK collector.
    This implementation provides the data structures without
    requiring the opentelemetry-sdk dependency.
    """

    def __init__(self, service_name: str = "preflight"):
        self._service_name = service_name
        self._spans: list[SpanRecord] = []
        self._max_spans = 10_000

    def start_span(
        self, operation: str, trace_id: str = "", **attributes: Any
    ) -> SpanRecord:
        import secrets
        span = SpanRecord(
            trace_id=trace_id or secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            operation=operation,
            start_time=time.time(),
            attributes={"service.name": self._service_name, **attributes},
        )
        return span

    def end_span(self, span: SpanRecord, status: str = "ok") -> None:
        span.end_time = time.time()
        span.status = status
        self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[self._max_spans // 2:]

    def export_otlp_json(self) -> list[dict[str, Any]]:
        """Export spans in OTLP-compatible JSON format."""
        return [
            {
                "traceId": s.trace_id,
                "spanId": s.span_id,
                "operationName": s.operation,
                "startTime": int(s.start_time * 1_000_000),
                "duration": int(s.duration_ms * 1000),
                "status": s.status,
                "attributes": s.attributes,
                "events": s.events,
                "serviceName": self._service_name,
            }
            for s in self._spans
        ]

    @property
    def span_count(self) -> int:
        return len(self._spans)
