"""Tests for TrustKernel deterministic planner."""

import pytest
from trust_kernel.planner import DeterministicPlanner, ExecutionDAG
from trust_kernel.models import (
    ExecutionEnvelope,
    StructuredIntent,
    ActionType,
    MutabilityClass,
)


def _make_envelope(
    action_id: str = "act-1",
    tool_name: str = "read_data",
    targets: list[str] | None = None,
    changes: list[str] | None = None,
    action_type: ActionType = ActionType.READ,
    cost: float = 0.0,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        action_id=action_id,
        agent_id="test-agent",
        tool_name=tool_name,
        resource_targets=targets or [],
        intent=StructuredIntent(
            goal=f"Test {tool_name}",
            reasoning_summary=f"Testing {tool_name}",
            action_type=action_type,
            estimated_cost=cost,
            expected_state_changes=changes or [],
        ),
    )


class TestDeterministicPlanner:
    def setup_method(self):
        self.planner = DeterministicPlanner()

    def test_plan_single_action(self):
        envelope = _make_envelope()
        dag = self.planner.plan_single(envelope)
        assert isinstance(dag, ExecutionDAG)
        assert len(dag.nodes) == 1
        assert not dag.has_cycles

    def test_plan_multiple_independent_actions(self):
        envelopes = [
            _make_envelope("act-1", "read_users", ["/users"]),
            _make_envelope("act-2", "read_orders", ["/orders"]),
        ]
        dag = self.planner.plan(envelopes)
        assert len(dag.nodes) == 2
        assert not dag.has_cycles
        assert len(dag.execution_order) == 2

    def test_plan_dependent_actions(self):
        envelopes = [
            _make_envelope("act-1", "write_users", ["/users"], ["users updated"],
                          ActionType.WRITE),
            _make_envelope("act-2", "read_users", ["/users"]),
        ]
        dag = self.planner.plan(envelopes)
        assert len(dag.nodes) == 2
        assert len(dag.edges) > 0

    def test_dag_state_hashes_annotated(self):
        envelope = _make_envelope(changes=["field updated"])
        dag = self.planner.plan_single(envelope)
        node = list(dag.nodes.values())[0]
        assert node.predicted_pre_hash != ""
        assert node.predicted_post_hash != ""
        assert node.predicted_pre_hash != node.predicted_post_hash

    def test_cost_aggregation(self):
        envelopes = [
            _make_envelope("act-1", "api_call_1", cost=10.0),
            _make_envelope("act-2", "api_call_2", cost=25.0),
        ]
        dag = self.planner.plan(envelopes)
        assert dag.total_estimated_cost == 35.0

    def test_critical_path(self):
        envelope = _make_envelope()
        dag = self.planner.plan_single(envelope)
        assert len(dag.critical_path) >= 1

    def test_dag_to_dict(self):
        envelope = _make_envelope()
        dag = self.planner.plan_single(envelope)
        d = dag.to_dict()
        assert "dag_id" in d
        assert d["node_count"] == 1
        assert "has_cycles" in d
