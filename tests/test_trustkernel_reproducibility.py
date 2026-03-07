"""Tests for TrustKernel reproducibility engine."""

import pytest
from trust_kernel.reproducibility import ReproducibilityEngine
from trust_kernel.models import ExecutionEnvelope, StateSnapshot, StructuredIntent


def _make_envelope():
    return ExecutionEnvelope(
        agent_id="test-agent",
        tool_name="update_record",
        arguments={"id": 42, "name": "test"},
        intent=StructuredIntent(
            goal="Update user record",
            reasoning_summary="Modifying user data",
        ),
    )


class TestReproducibilityEngine:
    def setup_method(self):
        self.engine = ReproducibilityEngine()

    def test_create_manifest(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id,
            agent_id=env.agent_id,
            entries={"name": "old_value"},
        )
        manifest = self.engine.create_manifest(
            env, pre_state, model_version="gpt-4o", model_seed=42
        )
        assert manifest.action_id == env.action_id
        assert manifest.model_version == "gpt-4o"
        assert manifest.model_seed == 42

    def test_get_manifest(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id, agent_id=env.agent_id, entries={}
        )
        self.engine.create_manifest(env, pre_state)
        retrieved = self.engine.get_manifest(env.action_id)
        assert retrieved is not None

    def test_export_manifest(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id, agent_id=env.agent_id, entries={"x": 1}
        )
        self.engine.create_manifest(env, pre_state)
        exported = self.engine.export_manifest(env.action_id)
        assert "manifest_id" in exported
        assert "manifest_hash" in exported
        assert "pre_state_snapshot" in exported

    def test_validate_replay_success(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id, agent_id=env.agent_id, entries={}
        )
        manifest = self.engine.create_manifest(
            env, pre_state,
            expected_result={"verdict": "allow", "risk": 0.1},
        )
        result = self.engine.validate_replay(
            manifest, {"verdict": "allow", "risk": 0.1}
        )
        assert result["valid"]
        assert result["fidelity"] == 1.0

    def test_validate_replay_mismatch(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id, agent_id=env.agent_id, entries={}
        )
        manifest = self.engine.create_manifest(
            env, pre_state,
            expected_result={"verdict": "allow"},
        )
        result = self.engine.validate_replay(
            manifest, {"verdict": "block"}
        )
        assert not result["valid"]
        assert len(result["mismatches"]) > 0

    def test_validate_replay_no_expected(self):
        env = _make_envelope()
        pre_state = StateSnapshot(
            action_id=env.action_id, agent_id=env.agent_id, entries={}
        )
        manifest = self.engine.create_manifest(env, pre_state)
        result = self.engine.validate_replay(manifest, {"anything": True})
        assert result["valid"]
