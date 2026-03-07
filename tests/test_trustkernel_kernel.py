"""Tests for TrustKernel main orchestrator."""

import asyncio
import pytest
from trust_kernel.kernel import TrustKernel, TrustKernelConfig
from trust_kernel.models import (
    CostBudget,
    ExecutionEnvelope,
    MutabilityClass,
    StructuredIntent,
    Verdict,
)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(coro, loop):
    return loop.run_until_complete(coro)


def _make_envelope(
    tool_name="read_data",
    reversible=True,
    cost=0.0,
    confidence=0.9,
    mutability="reversible",
):
    return ExecutionEnvelope(
        agent_id="test-agent",
        tool_name=tool_name,
        arguments={"query": "SELECT * FROM users"},
        intent=StructuredIntent(
            goal=f"Execute {tool_name}",
            reasoning_summary=f"Need to {tool_name}",
            reversible=reversible,
            estimated_cost=cost,
            confidence=confidence,
            mutability_class=MutabilityClass(mutability),
            expected_state_changes=["data read"],
        ),
    )


class TestTrustKernel:
    def test_basic_execution(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope()
        result = _run(kernel.execute(env), event_loop)

        assert result.verdict == Verdict.ALLOW
        assert result.dee.agent_signature != ""
        assert result.dee.policy_signature != ""
        assert result.pipeline_time_ms > 0

    def test_high_risk_blocks(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(
            db_path=":memory:", risk_threshold=0.5
        ))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope(
            tool_name="delete_all",
            reversible=False,
            mutability="destructive",
            confidence=0.3,
            cost=500,
        )
        result = _run(kernel.execute(env, risk_score=0.9), event_loop)

        assert result.verdict in (Verdict.BLOCK, Verdict.REQUIRE_APPROVAL)

    def test_irreversible_requires_approval(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope(reversible=False)
        result = _run(kernel.execute(env, risk_score=0.1), event_loop)

        assert result.verdict == Verdict.REQUIRE_APPROVAL
        assert result.consensus_request_id is not None

    def test_irreversible_with_consent(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope(reversible=False)
        result = _run(kernel.execute(
            env, risk_score=0.1, operator_consent=True
        ), event_loop)

        assert result.verdict == Verdict.ALLOW

    def test_ledger_records_action(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope()
        _run(kernel.execute(env), event_loop)

        records = _run(kernel.ledger.query(), event_loop)
        assert len(records) == 1

    def test_ledger_integrity(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        for i in range(5):
            env = _make_envelope(tool_name=f"tool_{i}")
            _run(kernel.execute(env), event_loop)

        valid, count = _run(kernel.verify_ledger_integrity(), event_loop)
        assert valid
        assert count == 5

    def test_cost_budget_enforcement(self, event_loop):
        budget = CostBudget(total_budget=10.0, max_single_action=5.0)
        kernel = TrustKernel(TrustKernelConfig(
            db_path=":memory:", budget=budget
        ))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope(cost=20.0)
        result = _run(kernel.execute(env), event_loop)
        assert result.verdict == Verdict.BLOCK
        assert any(a.metric == "cost" for a in result.cost_alerts)

    def test_reproducibility_manifest(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope()
        _run(kernel.execute(env), event_loop)

        manifest = kernel.reproducibility.get_manifest(env.action_id)
        assert manifest is not None
        assert manifest.action_id == env.action_id

    def test_consensus_approval_flow(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope(reversible=False)
        result = _run(kernel.execute(env, risk_score=0.1), event_loop)
        req_id = result.consensus_request_id
        assert req_id is not None

        approved = _run(kernel.approve_consensus(
            req_id, "operator-1", "Looks safe"
        ), event_loop)
        assert approved

    def test_stats(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope()
        _run(kernel.execute(env), event_loop)

        stats = _run(kernel.get_ledger_stats(), event_loop)
        assert stats["total_records"] >= 1
        assert "cost_usage" in stats

    def test_result_to_dict(self, event_loop):
        kernel = TrustKernel(TrustKernelConfig(db_path=":memory:"))
        _run(kernel.initialize(), event_loop)

        env = _make_envelope()
        result = _run(kernel.execute(env), event_loop)
        d = result.to_dict()

        assert "verdict" in d
        assert "risk_score" in d
        assert "signatures" in d
        assert "verification" in d
