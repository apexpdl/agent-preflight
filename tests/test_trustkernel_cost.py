"""Tests for TrustKernel cost governor."""

import pytest
from trust_kernel.cost_governor import CostGovernor
from trust_kernel.models import CostBudget, ExecutionEnvelope, StructuredIntent


def _make_envelope(cost=0.0, tool_name="test_tool"):
    return ExecutionEnvelope(
        agent_id="test-agent",
        tool_name=tool_name,
        intent=StructuredIntent(
            goal="Test",
            reasoning_summary="Testing",
            estimated_cost=cost,
        ),
    )


class TestCostGovernor:
    def test_within_budget(self):
        gov = CostGovernor(budget=CostBudget(total_budget=100.0))
        env = _make_envelope(cost=10.0)
        ok, alerts = gov.can_execute(env)
        assert ok
        assert not any(a.alert_type == "blocked" for a in alerts)

    def test_exceeds_budget(self):
        gov = CostGovernor(budget=CostBudget(total_budget=5.0))
        env = _make_envelope(cost=10.0)
        ok, alerts = gov.can_execute(env)
        assert not ok
        assert any(a.metric == "cost" for a in alerts)

    def test_exceeds_single_action_limit(self):
        gov = CostGovernor(budget=CostBudget(
            total_budget=1000.0, max_single_action=5.0
        ))
        env = _make_envelope(cost=10.0)
        ok, alerts = gov.can_execute(env)
        assert not ok

    def test_charge_updates_budget(self):
        gov = CostGovernor(budget=CostBudget(total_budget=100.0))
        env = _make_envelope(cost=25.0)
        gov.charge(env)
        assert gov.budget.spent == 25.0
        assert gov.budget.remaining == 75.0

    def test_tool_invocation_limit(self):
        gov = CostGovernor(budget=CostBudget(tool_invocation_limit=2))
        env = _make_envelope()
        gov.charge(env)
        gov.charge(env)
        ok, alerts = gov.can_execute(env)
        assert not ok
        assert any(a.metric == "tool_invocations" for a in alerts)

    def test_budget_warning_threshold(self):
        gov = CostGovernor(
            budget=CostBudget(total_budget=100.0),
            warning_threshold=0.8,
        )
        env = _make_envelope(cost=85.0)
        ok, alerts = gov.can_execute(env)
        assert ok
        assert any(a.alert_type == "warning" for a in alerts)

    def test_usage_summary(self):
        gov = CostGovernor(budget=CostBudget(total_budget=100.0))
        env = _make_envelope(cost=30.0)
        gov.charge(env, tokens_used=1000)
        summary = gov.get_usage_summary()
        assert summary["cost"]["spent"] == 30.0
        assert summary["tokens"]["used"] == 1000

    def test_recursion_tracking(self):
        gov = CostGovernor(budget=CostBudget(recursion_depth_limit=3))
        env = _make_envelope(tool_name="recursive_tool")
        for _ in range(3):
            gov.charge(env)
        ok, alerts = gov.can_execute(env)
        assert not ok
        assert any(a.metric == "recursion" for a in alerts)

    def test_reset_recursion(self):
        gov = CostGovernor(budget=CostBudget(recursion_depth_limit=2))
        env = _make_envelope(tool_name="t1")
        gov.charge(env)
        gov.charge(env)
        gov.reset_recursion("t1")
        ok, _ = gov.can_execute(env)
        assert ok
