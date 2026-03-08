"""Tests for Safety Snapshot generation."""

import pytest
from trust_kernel.snapshot import SafetySnapshot


class TestSafetySnapshot:
    def test_basic_creation(self):
        snap = SafetySnapshot()
        assert snap.snapshot_id
        assert snap.total_actions == 0

    def test_add_actions(self):
        snap = SafetySnapshot()
        snap.add_action(verdict="allow", risk_score=0.1, pipeline_ms=3.0)
        snap.add_action(verdict="block", risk_score=0.9, cost_prevented=500.0, pipeline_ms=10.0)
        snap.add_action(verdict="warn", risk_score=0.5, pipeline_ms=7.0)

        assert snap.total_actions == 3
        assert snap.blocked_actions == 1
        assert snap.warned_actions == 1
        assert snap.allowed_actions == 1
        assert snap.total_cost_prevented == 500.0
        assert snap.highest_risk_score == 0.9

    def test_risk_distribution(self):
        snap = SafetySnapshot()
        snap.add_action(verdict="allow", risk_score=0.1)  # low
        snap.add_action(verdict="allow", risk_score=0.35)  # medium
        snap.add_action(verdict="warn", risk_score=0.6)  # high
        snap.add_action(verdict="block", risk_score=0.85)  # critical

        assert snap.risk_distribution["low"] == 1
        assert snap.risk_distribution["medium"] == 1
        assert snap.risk_distribution["high"] == 1
        assert snap.risk_distribution["critical"] == 1

    def test_to_dict(self):
        snap = SafetySnapshot(period_label="Test Period")
        snap.add_action(verdict="allow", risk_score=0.2)
        d = snap.to_dict()
        assert d["period"] == "Test Period"
        assert d["total_actions"] == 1
        assert d["allowed"] == 1
        assert "snapshot_id" in d
        assert "created_at" in d

    def test_html_generation(self):
        snap = SafetySnapshot(period_label="HTML Test")
        snap.add_action(verdict="block", risk_score=0.8, cost_prevented=1000.0)
        html = snap.generate_html()
        assert "Preflight" in html
        assert "HTML Test" in html
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html

    def test_summary_text(self):
        snap = SafetySnapshot(period_label="Text Test")
        snap.add_action(verdict="allow", risk_score=0.1)
        snap.add_action(verdict="block", risk_score=0.9, cost_prevented=250.0)
        text = snap.generate_summary_text()
        assert "Preflight" in text
        assert "Blocked: 1" in text
        assert "$250.00" in text

    def test_badge_svg_safe(self):
        snap = SafetySnapshot()
        snap.add_action(verdict="allow", risk_score=0.1)
        svg = snap.generate_badge_svg()
        assert "<svg" in svg
        assert "preflight" in svg
        assert "safe" in svg

    def test_badge_svg_with_blocks(self):
        snap = SafetySnapshot()
        for _ in range(5):
            snap.add_action(verdict="block", risk_score=0.8)
        for _ in range(5):
            snap.add_action(verdict="allow", risk_score=0.1)
        svg = snap.generate_badge_svg()
        assert "blocked" in svg

    def test_average_risk_running_calculation(self):
        snap = SafetySnapshot()
        snap.add_action(verdict="allow", risk_score=0.2)
        snap.add_action(verdict="allow", risk_score=0.4)
        assert abs(snap.average_risk_score - 0.3) < 0.001

    def test_pipeline_avg_ms(self):
        snap = SafetySnapshot()
        snap.add_action(verdict="allow", risk_score=0.1, pipeline_ms=10.0)
        snap.add_action(verdict="allow", risk_score=0.1, pipeline_ms=20.0)
        assert abs(snap.pipeline_avg_ms - 15.0) < 0.001
