"""Tests for Risk Memory module."""

import pytest
from agent_preflight.atf.risk_memory import RiskMemory, RiskRecall


class TestRiskMemory:
    def setup_method(self):
        self.memory = RiskMemory()

    def test_initial_recall_empty(self):
        recall = self.memory.recall("unknown_tool", {})
        assert not recall.previously_blocked
        assert recall.tool_block_rate == 0.0
        assert recall.risk_adjustment == 0.0
        assert recall.memory_flags == []

    def test_record_and_recall_allowed(self):
        self.memory.record("read_file", {"path": "/tmp/test"}, 0.1, "allow", [], "agent-1")
        recall = self.memory.recall("read_file", {"path": "/tmp/test"})
        assert not recall.previously_blocked
        assert recall.pattern_count == 1

    def test_record_and_recall_blocked(self):
        self.memory.record("delete_all", {"table": "users"}, 0.95, "block", ["destructive_tool"], "agent-1")
        recall = self.memory.recall("delete_all", {"table": "users"})
        assert recall.previously_blocked
        assert recall.risk_adjustment > 0
        assert len(recall.memory_flags) > 0

    def test_tool_block_rate(self):
        for _ in range(3):
            self.memory.record("risky_tool", {}, 0.8, "block", [], "a")
        for _ in range(7):
            self.memory.record("risky_tool", {}, 0.2, "allow", [], "a")

        recall = self.memory.recall("risky_tool", {})
        assert abs(recall.tool_block_rate - 0.3) < 0.001

    def test_frequently_blocked_tool_flag(self):
        for _ in range(6):
            self.memory.record("bad_tool", {}, 0.9, "block", [], "a")
        for _ in range(4):
            self.memory.record("bad_tool", {}, 0.3, "allow", [], "a")

        recall = self.memory.recall("bad_tool", {})
        assert "tool_frequently_blocked" in recall.memory_flags

    def test_repeated_recent_blocks(self):
        for _ in range(3):
            self.memory.record("danger_tool", {"x": "1"}, 0.9, "block", [], "a")

        recall = self.memory.recall("danger_tool", {"x": "1"})
        assert "repeated_recent_blocks" in recall.memory_flags

    def test_risk_adjustment_capped(self):
        for _ in range(100):
            self.memory.record("tool", {}, 0.99, "block", [], "a")

        recall = self.memory.recall("tool", {})
        assert recall.risk_adjustment <= 0.3

    def test_different_patterns(self):
        self.memory.record("tool", {"a": "1"}, 0.5, "block", [], "a")
        self.memory.record("tool", {"b": "2"}, 0.1, "allow", [], "a")

        recall_a = self.memory.recall("tool", {"a": "1"})
        recall_b = self.memory.recall("tool", {"b": "2"})
        assert recall_a.previously_blocked
        assert not recall_b.previously_blocked

    def test_get_stats(self):
        self.memory.record("t1", {}, 0.5, "allow", [], "a")
        self.memory.record("t2", {}, 0.9, "block", [], "b")

        stats = self.memory.get_stats()
        assert stats["total_patterns"] >= 1
        assert stats["unique_tools"] == 2

    def test_max_entries_eviction(self):
        memory = RiskMemory(max_entries=5)
        for i in range(10):
            memory.record(f"tool_{i}", {}, 0.5, "allow", [], "a")
        assert len(memory._patterns) <= 5

    def test_recent_blocks_ring_buffer(self):
        for i in range(150):
            self.memory.record("tool", {}, 0.9, "block", [], "a")
        assert len(self.memory._recent_blocks) <= 100

    def test_to_dict(self):
        recall = RiskRecall(previously_blocked=True, risk_adjustment=0.15)
        d = recall.to_dict()
        assert d["previously_blocked"] is True
        assert d["risk_adjustment"] == 0.15

    def test_pattern_key_deterministic(self):
        key1 = RiskMemory._pattern_key("tool", {"a": "1", "b": "2"})
        key2 = RiskMemory._pattern_key("tool", {"b": "2", "a": "1"})
        assert key1 == key2

    def test_pattern_key_case_insensitive_tool(self):
        key1 = RiskMemory._pattern_key("DeleteFile", {})
        key2 = RiskMemory._pattern_key("deletefile", {})
        assert key1 == key2
