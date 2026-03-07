"""Tests for display module."""

import pytest
from agent_preflight.display import (
    render_interception,
    render_startup_banner,
    render_stats,
    _risk_label,
    _risk_meter,
)


class TestDisplay:
    def test_render_interception_block(self):
        output = render_interception(
            tool_name="delete_database",
            verdict="block",
            risk_score=0.92,
            flags=["destructive_tool", "irreversible"],
            human_summary="Attempted to delete production database",
            pipeline_time_ms=12.5,
        )
        assert "BLOCKED" in output
        assert "delete_database" in output
        assert "92%" in output

    def test_render_interception_allow(self):
        output = render_interception(
            tool_name="get_user",
            verdict="allow",
            risk_score=0.05,
            flags=[],
            pipeline_time_ms=2.1,
        )
        assert "ALLOWED" in output
        assert "get_user" in output

    def test_render_interception_warn(self):
        output = render_interception(
            tool_name="send_email",
            verdict="warn",
            risk_score=0.55,
            flags=["external_communication"],
        )
        assert "WARNING" in output

    def test_render_interception_with_correction(self):
        output = render_interception(
            tool_name="rm_rf",
            verdict="block",
            risk_score=0.98,
            flags=["destructive_tool"],
            correction={
                "suggestions": ["Use targeted deletion instead of rm -rf"],
            },
        )
        assert "Suggested fix" in output
        assert "targeted deletion" in output

    def test_render_interception_with_simulation(self):
        output = render_interception(
            tool_name="deploy",
            verdict="warn",
            risk_score=0.7,
            flags=[],
            simulation={"failure_probability": 0.45, "cascade_risk": 0.2},
        )
        assert "failure" in output
        assert "cascade" in output

    def test_render_interception_with_passport(self):
        output = render_interception(
            tool_name="read_file",
            verdict="allow",
            risk_score=0.05,
            flags=[],
            passport_id="abc12345-6789",
        )
        assert "passport:abc12345" in output

    def test_render_startup_banner(self):
        output = render_startup_banner()
        assert "Preflight" in output
        assert "enabled" in output

    def test_render_stats(self):
        output = render_stats({
            "total": 100,
            "blocked": 10,
            "warned": 15,
            "allowed": 75,
        })
        assert "75" in output
        assert "10" in output
        assert "15" in output
        assert "100" in output

    def test_risk_label(self):
        assert _risk_label(0.9) == "Critical"
        assert _risk_label(0.6) == "High"
        assert _risk_label(0.35) == "Medium"
        assert _risk_label(0.1) == "Low"

    def test_risk_meter_format(self):
        meter = _risk_meter(0.5)
        assert "50%" in meter

    def test_render_interception_require_approval(self):
        output = render_interception(
            tool_name="wire_transfer",
            verdict="require_approval",
            risk_score=0.8,
            flags=["financial_operation"],
        )
        assert "NEEDS APPROVAL" in output

    def test_long_summary_truncated(self):
        long_summary = "A" * 200
        output = render_interception(
            tool_name="tool",
            verdict="block",
            risk_score=0.9,
            flags=[],
            human_summary=long_summary,
        )
        assert "..." in output

    def test_many_flags_limited(self):
        flags = [f"flag_{i}" for i in range(10)]
        output = render_interception(
            tool_name="tool",
            verdict="warn",
            risk_score=0.6,
            flags=flags,
        )
        # Should only show first 4 flags
        assert "flag 0" in output
        assert "flag 3" in output
