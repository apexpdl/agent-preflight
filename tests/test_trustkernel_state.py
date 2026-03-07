"""Tests for TrustKernel state engine."""

import pytest
from trust_kernel.state_engine import StateEngine
from trust_kernel.models import ExecutionEnvelope, StructuredIntent


def _make_envelope(action_id="act-1"):
    return ExecutionEnvelope(
        action_id=action_id,
        agent_id="test-agent",
        tool_name="update_record",
        intent=StructuredIntent(
            goal="Update user record",
            reasoning_summary="Modifying user data",
            expected_state_changes=["user.name changed"],
        ),
    )


class TestStateEngine:
    def setup_method(self):
        self.engine = StateEngine()

    def test_capture_pre_state(self):
        env = _make_envelope()
        snapshot = self.engine.capture_pre_state(env, {"name": "Alice", "age": 30})
        assert snapshot.state_hash != ""
        assert snapshot.action_id == "act-1"
        assert snapshot.entries["name"] == "Alice"

    def test_capture_post_state(self):
        snapshot = self.engine.capture_post_state(
            "act-1", "agent-1", {"name": "Bob", "age": 30}
        )
        assert snapshot.state_hash != ""

    def test_predict_post_state(self):
        env = _make_envelope()
        pre = self.engine.capture_pre_state(env, {"name": "Alice"})
        predicted = self.engine.predict_post_state(pre, ["name changed"])
        assert predicted != pre.state_hash

    def test_compute_diff_no_changes(self):
        env = _make_envelope()
        pre = self.engine.capture_pre_state(env, {"x": 1})
        predicted = pre.state_hash
        post = self.engine.capture_post_state("act-1", "agent-1", {"x": 1})
        diff = self.engine.compute_diff("act-1", pre, predicted, post)
        assert diff.deviation_pct == 0.0
        assert diff.fidelity_score == 1.0
        assert not diff.exceeds_threshold

    def test_compute_diff_with_changes(self):
        env = _make_envelope()
        pre = self.engine.capture_pre_state(env, {"x": 1, "y": 2})
        predicted = self.engine.predict_post_state(pre, ["x changed"])
        post = self.engine.capture_post_state("act-1", "agent-1", {"x": 99, "y": 2})
        diff = self.engine.compute_diff("act-1", pre, predicted, post)
        assert diff.deviation_pct > 0
        assert len(diff.field_diffs) > 0

    def test_get_snapshot(self):
        env = _make_envelope()
        self.engine.capture_pre_state(env, {"data": True})
        snap = self.engine.get_snapshot("act-1")
        assert snap is not None
        assert snap.entries["data"] is True

    def test_clear_snapshots(self):
        env = _make_envelope()
        self.engine.capture_pre_state(env, {"data": True})
        self.engine.clear_snapshots()
        assert self.engine.get_snapshot("act-1") is None
