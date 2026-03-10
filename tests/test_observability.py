"""Tests for the observability layer."""

import logging
import time

import pytest
from trust_kernel.observability import (
    StructuredLogger, MetricsCollector, SpanExporter, SpanRecord,
)


class TestStructuredLogger:
    def test_log_entry(self):
        logger = StructuredLogger(name="test", level=logging.CRITICAL)
        entry = logger.info("test_event", agent_id="a1", risk=0.5)
        assert entry["event"] == "test_event"
        assert entry["level"] == "info"
        assert entry["agent_id"] == "a1"
        assert "timestamp" in entry

    def test_log_levels(self):
        logger = StructuredLogger(name="levels", level=logging.CRITICAL)
        logger.info("i")
        logger.warning("w")
        logger.error("e")
        logger.critical("c")
        assert logger.entry_count == 4

    def test_get_entries_with_filter(self):
        logger = StructuredLogger(name="filter", level=logging.CRITICAL)
        logger.info("a")
        logger.warning("b")
        logger.info("c")
        infos = logger.get_entries(level="info")
        assert len(infos) == 2
        warnings = logger.get_entries(level="warning")
        assert len(warnings) == 1

    def test_get_entries_by_event(self):
        logger = StructuredLogger(name="event_filter", level=logging.CRITICAL)
        logger.info("action_evaluated")
        logger.info("action_blocked")
        logger.info("action_evaluated")
        found = logger.get_entries(event="action_evaluated")
        assert len(found) == 2

    def test_rotation(self):
        logger = StructuredLogger(name="rotation", level=logging.CRITICAL, max_entries=10)
        for i in range(15):
            logger.info(f"event_{i}")
        # Should have rotated to ~10 entries
        assert logger.entry_count <= 10


class TestMetricsCollector:
    def test_counter(self):
        mc = MetricsCollector()
        mc.inc_counter("requests_total")
        mc.inc_counter("requests_total")
        data = mc.export_json()
        assert data["counters"]["requests_total"] == 2.0

    def test_gauge(self):
        mc = MetricsCollector()
        mc.set_gauge("active_agents", 5)
        mc.set_gauge("active_agents", 3)
        data = mc.export_json()
        assert data["gauges"]["active_agents"] == 3

    def test_histogram(self):
        mc = MetricsCollector()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            mc.observe_histogram("latency", v)
        data = mc.export_json()
        hist = data["histograms"]["latency"]
        assert hist["count"] == 5
        assert hist["min"] == 1.0
        assert hist["max"] == 5.0

    def test_record_action(self):
        mc = MetricsCollector()
        mc.record_action(
            verdict="allow", risk_score=0.3, pipeline_ms=5.0,
            tool_name="file_read", agent_id="agent-1",
        )
        mc.record_action(
            verdict="block", risk_score=0.9, pipeline_ms=15.0,
            tool_name="file_delete", agent_id="agent-1",
        )
        data = mc.export_json()
        # Should have counters for both verdicts
        assert any("allow" in k for k in data["counters"])
        assert any("block" in k for k in data["counters"])

    def test_prometheus_export_format(self):
        mc = MetricsCollector()
        mc.inc_counter("test_counter")
        mc.set_gauge("test_gauge", 42)
        mc.observe_histogram("test_hist", 1.0)
        output = mc.export_prometheus()
        assert "# TYPE test_counter counter" in output
        assert "# TYPE test_gauge gauge" in output
        assert "test_hist_count" in output

    def test_labels(self):
        mc = MetricsCollector()
        mc.inc_counter("requests", method="GET")
        mc.inc_counter("requests", method="POST")
        data = mc.export_json()
        assert 'requests{method="GET"}' in data["counters"]
        assert 'requests{method="POST"}' in data["counters"]


class TestSpanExporter:
    def test_start_and_end_span(self):
        se = SpanExporter(service_name="test-svc")
        span = se.start_span("evaluate_risk", agent_id="a1")
        assert span.trace_id
        assert span.span_id
        assert span.operation == "evaluate_risk"
        time.sleep(0.01)
        se.end_span(span, status="ok")
        assert span.end_time > span.start_time
        assert span.duration_ms > 0
        assert se.span_count == 1

    def test_otlp_export(self):
        se = SpanExporter()
        span = se.start_span("test_op")
        se.end_span(span)
        exported = se.export_otlp_json()
        assert len(exported) == 1
        assert exported[0]["operationName"] == "test_op"
        assert "traceId" in exported[0]
        assert "spanId" in exported[0]
        assert exported[0]["status"] == "ok"

    def test_span_attributes(self):
        se = SpanExporter()
        span = se.start_span("op", tool="file_write", risk=0.5)
        se.end_span(span)
        exported = se.export_otlp_json()
        attrs = exported[0]["attributes"]
        assert attrs["tool"] == "file_write"
        assert attrs["risk"] == 0.5

    def test_multiple_spans(self):
        se = SpanExporter()
        for i in range(5):
            span = se.start_span(f"op_{i}")
            se.end_span(span)
        assert se.span_count == 5
        exported = se.export_otlp_json()
        assert len(exported) == 5
