"""Tests for Agent Behavior Analytics module."""

import pytest
from agent_preflight.atf.analytics import AgentAnalytics, AgentProfile


class TestAgentAnalytics:
    def setup_method(self):
        self.analytics = AgentAnalytics()

    def test_record_creates_profile(self):
        self.analytics.record(
            agent_id="agent-1",
            tool_name="read_file",
            risk_score=0.1,
            verdict="allow",
        )
        profile = self.analytics.get_profile("agent-1")
        assert profile is not None
        assert profile.total_actions == 1
        assert profile.allowed_actions == 1

    def test_record_multiple_actions(self):
        for i in range(5):
            self.analytics.record(
                agent_id="agent-1",
                tool_name="read_file",
                risk_score=0.1,
                verdict="allow",
            )
        self.analytics.record(
            agent_id="agent-1",
            tool_name="delete_file",
            risk_score=0.9,
            verdict="block",
            flags=["destructive_tool"],
        )
        profile = self.analytics.get_profile("agent-1")
        assert profile.total_actions == 6
        assert profile.allowed_actions == 5
        assert profile.blocked_actions == 1
        assert profile.max_risk_score == 0.9

    def test_block_rate(self):
        for _ in range(3):
            self.analytics.record("a", "tool", 0.9, "block")
        for _ in range(7):
            self.analytics.record("a", "tool", 0.1, "allow")

        profile = self.analytics.get_profile("a")
        assert abs(profile.block_rate - 0.3) < 0.001

    def test_average_risk(self):
        self.analytics.record("a", "t1", 0.2, "allow")
        self.analytics.record("a", "t2", 0.8, "allow")
        profile = self.analytics.get_profile("a")
        assert abs(profile.average_risk - 0.5) < 0.001

    def test_danger_score(self):
        # Safe agent
        self.analytics.record("safe", "read", 0.05, "allow")
        safe = self.analytics.get_profile("safe")
        assert safe.danger_score < 0.3

        # Dangerous agent
        for _ in range(5):
            self.analytics.record("danger", "delete", 0.95, "block", ["destructive_tool"])
        danger = self.analytics.get_profile("danger")
        assert danger.danger_score > 0.5

    def test_tool_usage_tracking(self):
        self.analytics.record("a", "read_file", 0.1, "allow")
        self.analytics.record("a", "read_file", 0.1, "allow")
        self.analytics.record("a", "delete_file", 0.8, "block")

        profile = self.analytics.get_profile("a")
        assert profile.tool_usage["read_file"] == 2
        assert profile.tool_usage["delete_file"] == 1

    def test_flag_tracking(self):
        self.analytics.record("a", "t", 0.9, "block", flags=["destructive_tool", "irreversible"])
        self.analytics.record("a", "t", 0.8, "block", flags=["destructive_tool"])

        profile = self.analytics.get_profile("a")
        assert profile.flag_counts["destructive_tool"] == 2
        assert profile.flag_counts["irreversible"] == 1

    def test_loop_detection(self):
        # Call same tool 10 times in a row
        for _ in range(10):
            self.analytics.record("looper", "same_tool", 0.3, "allow")

        profile = self.analytics.get_profile("looper")
        assert profile.loop_detections > 0

    def test_get_all_profiles_sorted(self):
        # Create safe and dangerous agents
        self.analytics.record("safe", "read", 0.05, "allow")
        for _ in range(5):
            self.analytics.record("danger", "delete", 0.95, "block")

        profiles = self.analytics.get_all_profiles()
        assert len(profiles) == 2
        assert profiles[0].agent_id == "danger"

    def test_get_summary(self):
        self.analytics.record("a", "t", 0.5, "allow")
        self.analytics.record("b", "t", 0.9, "block")

        summary = self.analytics.get_summary()
        assert summary["total_agents"] == 2
        assert summary["total_actions"] == 2
        assert summary["total_blocked"] == 1
        assert "agents" in summary

    def test_get_risky_agents(self):
        self.analytics.record("safe", "read", 0.05, "allow")
        for _ in range(10):
            self.analytics.record("risky", "delete", 0.95, "block")

        risky = self.analytics.get_risky_agents(threshold=0.5)
        assert len(risky) == 1
        assert risky[0].agent_id == "risky"

    def test_profile_to_dict(self):
        self.analytics.record("a", "t", 0.5, "allow", flags=["test"])
        profile = self.analytics.get_profile("a")
        d = profile.to_dict()
        assert d["agent_id"] == "a"
        assert d["total_actions"] == 1
        assert "average_risk" in d
        assert "danger_score" in d

    def test_recent_actions_ring_buffer(self):
        analytics = AgentAnalytics(max_recent=5)
        for i in range(10):
            analytics.record("a", f"tool_{i}", 0.1, "allow")

        profile = analytics.get_profile("a")
        assert len(profile.recent_actions) == 5

    def test_max_agents_eviction(self):
        analytics = AgentAnalytics(max_agents=3)
        for i in range(5):
            analytics.record(f"agent-{i}", "tool", 0.1, "allow")

        assert len(analytics._profiles) <= 3

    def test_unknown_agent_returns_none(self):
        assert self.analytics.get_profile("nonexistent") is None

    def test_warned_actions(self):
        self.analytics.record("a", "t", 0.5, "warn")
        profile = self.analytics.get_profile("a")
        assert profile.warned_actions == 1
