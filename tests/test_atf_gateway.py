"""Tests for ATF Gateway — full pipeline integration tests."""

import pytest
import pytest_asyncio
from agent_preflight.atf.config import ATFConfig, ExecutionMode
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent, Verdict
from agent_preflight.atf.plugins import ALL_PLUGINS


@pytest_asyncio.fixture
async def gateway():
    config = ATFConfig.for_mode(
        ExecutionMode.SAFE,
        database_path=":memory:",
        simulation_rollouts=10,  # Fast for tests
    )
    gw = ATFGateway(config)
    await gw.initialize()
    gw.register_plugins([p() for p in ALL_PLUGINS])
    return gw


def _low_risk_envelope():
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name="get_user",
        arguments={"id": "123"},
        intent=StructuredIntent(
            goal="Fetch user data",
            reasoning_summary="Display on dashboard",
            confidence=0.95,
        ),
    )


def _high_risk_envelope():
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name="delete_database",
        arguments={"target": "production", "path": "/prod/data.db"},
        resource_targets=["/prod/data.db"],
        intent=StructuredIntent(
            goal="Delete production database",
            reasoning_summary="Cleanup",
            irreversible=True,
            estimated_cost=0,
            confidence=0.4,
        ),
    )


def _financial_envelope():
    return ActionEnvelope(
        agent_id="finance-bot",
        tool_name="wire_transfer",
        arguments={"amount": 100000, "to": "external"},
        intent=StructuredIntent(
            goal="Transfer funds",
            reasoning_summary="Vendor payment",
            irreversible=True,
            estimated_cost=100000,
            confidence=0.8,
        ),
    )


class TestATFGateway:
    @pytest.mark.asyncio
    async def test_low_risk_allowed(self, gateway):
        result = await gateway.intercept_and_execute(_low_risk_envelope())
        assert result.verdict == Verdict.ALLOW
        assert result.risk_assessment.score < 0.5
        assert result.passport is not None
        assert result.human_summary

    @pytest.mark.asyncio
    async def test_high_risk_blocked(self, gateway):
        result = await gateway.intercept_and_execute(_high_risk_envelope())
        assert result.verdict in (Verdict.BLOCK, Verdict.WARN)
        assert result.risk_assessment.score > 0.3

    @pytest.mark.asyncio
    async def test_financial_risk(self, gateway):
        result = await gateway.intercept_and_execute(_financial_envelope())
        assert result.risk_assessment.score > 0.5
        assert "financial_operation" in result.risk_assessment.flags

    @pytest.mark.asyncio
    async def test_pipeline_timing(self, gateway):
        result = await gateway.intercept_and_execute(_low_risk_envelope())
        assert result.total_pipeline_time_ms > 0

    @pytest.mark.asyncio
    async def test_passport_signed(self, gateway):
        result = await gateway.intercept_and_execute(_low_risk_envelope())
        assert result.passport is not None
        assert gateway.passport_authority.verify(result.passport)

    @pytest.mark.asyncio
    async def test_human_summary_generated(self, gateway):
        result = await gateway.intercept_and_execute(_low_risk_envelope())
        assert "test-agent" in result.human_summary
        assert "Fetch user data" in result.human_summary

    @pytest.mark.asyncio
    async def test_agent_response_format(self, gateway):
        result = await gateway.intercept_and_execute(_low_risk_envelope())
        resp = result.to_agent_response()
        assert "verdict" in resp
        assert "risk_score" in resp
        assert "human_summary" in resp
        assert "passport_id" in resp

    @pytest.mark.asyncio
    async def test_db_logging(self, gateway):
        await gateway.intercept_and_execute(_low_risk_envelope())
        await gateway.intercept_and_execute(_high_risk_envelope())
        stats = await gateway.db.get_stats()
        assert stats["total_actions"] == 2

    @pytest.mark.asyncio
    async def test_policy_blocks(self, gateway):
        from agent_preflight.atf.policy_v2 import PolicyRule
        gateway.policy_engine.add_rule(
            PolicyRule("no_delete", 'tool matches "delete"', "block")
        )
        result = await gateway.intercept_and_execute(_high_risk_envelope())
        assert result.verdict == Verdict.BLOCK
        assert result.correction is not None
        assert len(result.correction.violations) > 0

    @pytest.mark.asyncio
    async def test_correction_feedback(self, gateway):
        from agent_preflight.atf.policy_v2 import PolicyRule
        gateway.policy_engine.add_rule(
            PolicyRule("no_delete", 'tool matches "delete"', "block")
        )
        result = await gateway.intercept_and_execute(_high_risk_envelope())
        assert result.correction is not None
        assert result.correction.declared_goal == "Delete production database"
        assert len(result.correction.suggestions) > 0


class TestATFConfig:
    def test_mode_presets(self):
        safe = ATFConfig.for_mode(ExecutionMode.SAFE)
        aggressive = ATFConfig.for_mode(ExecutionMode.AGGRESSIVE)
        assert safe.risk_threshold_mirror < aggressive.risk_threshold_mirror
        assert safe.simulation_rollouts > aggressive.simulation_rollouts

    def test_enterprise_mode(self):
        enterprise = ATFConfig.for_mode(ExecutionMode.ENTERPRISE)
        assert enterprise.drift_enabled
        assert enterprise.structured_logging
        assert enterprise.simulation_rollouts >= 200
