"""Tests for ATF Risk Engine v2."""

import pytest
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
from agent_preflight.atf.risk_engine import RiskEngine


def _make_envelope(tool_name="test_tool", **intent_overrides):
    intent_defaults = {"goal": "Test", "reasoning_summary": "Test"}
    intent_defaults.update(intent_overrides)
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name=tool_name,
        arguments={},
        intent=StructuredIntent(**intent_defaults),
    )


@pytest.fixture
def engine():
    return RiskEngine()


class TestRiskEngine:
    @pytest.mark.asyncio
    async def test_low_risk_read(self, engine):
        e = _make_envelope("get_user_profile")
        result = await engine.assess(e)
        assert result.score < 0.3
        assert not result.requires_mirror

    @pytest.mark.asyncio
    async def test_high_risk_delete(self, engine):
        e = _make_envelope("delete_database", irreversible=True)
        result = await engine.assess(e)
        assert result.score > 0.5
        assert "destructive_tool" in result.flags
        assert "irreversible" in result.flags

    @pytest.mark.asyncio
    async def test_financial_critical(self, engine):
        e = _make_envelope("wire_transfer", irreversible=True, estimated_cost=1000)
        result = await engine.assess(e)
        assert result.score > 0.7
        assert "financial_operation" in result.flags

    @pytest.mark.asyncio
    async def test_shell_execution(self, engine):
        e = _make_envelope("exec_shell_command")
        result = await engine.assess(e)
        assert "shell_execution" in result.flags

    @pytest.mark.asyncio
    async def test_sensitive_path(self, engine):
        e = ActionEnvelope(
            agent_id="test",
            tool_name="write_file",
            arguments={"path": "/etc/passwd"},
            intent=StructuredIntent(goal="Write", reasoning_summary="Test"),
        )
        result = await engine.assess(e)
        assert "sensitive_path" in result.flags

    @pytest.mark.asyncio
    async def test_low_confidence(self, engine):
        e = _make_envelope("some_tool", confidence=0.2)
        result = await engine.assess(e)
        assert "low_confidence" in result.flags

    @pytest.mark.asyncio
    async def test_drift_similarity_increases_risk(self, engine):
        e = _make_envelope("some_tool")
        r_no_drift = await engine.assess(e, drift_similarity=0.0)
        r_with_drift = await engine.assess(e, drift_similarity=0.8)
        assert r_with_drift.score > r_no_drift.score

    @pytest.mark.asyncio
    async def test_computation_time_fast(self, engine):
        e = _make_envelope("test")
        result = await engine.assess(e)
        assert result.computation_time_ms < 20  # Must be <20ms

    @pytest.mark.asyncio
    async def test_breakdown_populated(self, engine):
        e = _make_envelope("delete_records", irreversible=True)
        result = await engine.assess(e)
        assert len(result.breakdown) > 0

    @pytest.mark.asyncio
    async def test_update_weights(self, engine):
        e = _make_envelope("delete_all", irreversible=True)
        r1 = await engine.assess(e)
        engine.update_weights({"irreversible": 0.1})
        r2 = await engine.assess(e)
        assert r2.score < r1.score
