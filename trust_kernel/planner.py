"""
TrustKernel Deterministic Planner.

Accepts Intent objects and plans execution stepwise with dependency
resolution. Generates a DAG of actions, detects cycles and deadlocks,
and annotates actions with predicted pre/post-state hashes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional

from trust_kernel.models import ExecutionEnvelope, StructuredIntent


@dataclass
class DAGNode:
    """Single node in the execution DAG."""
    node_id: str
    action_id: str
    tool_name: str
    intent: StructuredIntent
    dependencies: list[str] = field(default_factory=list)
    predicted_pre_hash: str = ""
    predicted_post_hash: str = ""
    estimated_cost: float = 0.0
    estimated_risk: float = 0.0
    execution_order: int = -1


@dataclass
class ExecutionDAG:
    """Directed Acyclic Graph representing planned execution."""
    dag_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nodes: dict[str, DAGNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    has_cycles: bool = False
    cycle_details: list[list[str]] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    total_estimated_risk: float = 0.0
    critical_path: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dag_id": self.dag_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "execution_order": self.execution_order,
            "has_cycles": self.has_cycles,
            "total_estimated_cost": self.total_estimated_cost,
            "total_estimated_risk": self.total_estimated_risk,
            "critical_path_length": len(self.critical_path),
        }


class DeterministicPlanner:
    """Plans and validates execution order for a set of actions.

    Responsibilities:
    - Build DAG from action envelopes
    - Detect cycles and deadlocks
    - Compute topological execution order
    - Annotate with predicted state hashes
    - Estimate cumulative risk and cost
    """

    def plan(self, envelopes: list[ExecutionEnvelope]) -> ExecutionDAG:
        """Create an execution DAG from a list of action envelopes."""
        dag = ExecutionDAG()

        # Build nodes
        for env in envelopes:
            node = DAGNode(
                node_id=env.action_id,
                action_id=env.action_id,
                tool_name=env.tool_name,
                intent=StructuredIntent(
                    goal=env.intent.goal,
                    reasoning_summary=env.intent.reasoning_summary,
                    action_type=env.intent.action_type,
                    target_resource=env.intent.target_resource,
                    mutability_class=env.intent.mutability_class,
                    reversible=env.intent.reversible,
                    estimated_cost=env.intent.estimated_cost,
                    confidence=env.intent.confidence,
                    external_dependency_count=env.intent.external_dependency_count,
                    expected_state_changes=env.intent.expected_state_changes,
                    external_calls=env.intent.external_calls,
                ),
                estimated_cost=env.intent.estimated_cost,
            )
            dag.nodes[env.action_id] = node

        # Infer dependencies from resource targets and state changes
        self._infer_dependencies(dag, envelopes)

        # Detect cycles
        dag.has_cycles = self._detect_cycles(dag)
        if dag.has_cycles:
            dag.cycle_details = self._find_cycles(dag)

        # Compute topological order
        if not dag.has_cycles:
            dag.execution_order = self._topological_sort(dag)
            for i, node_id in enumerate(dag.execution_order):
                dag.nodes[node_id].execution_order = i

        # Compute critical path
        dag.critical_path = self._compute_critical_path(dag)

        # Annotate with predicted state hashes
        self._annotate_state_hashes(dag, envelopes)

        # Sum costs and risks
        dag.total_estimated_cost = sum(n.estimated_cost for n in dag.nodes.values())
        dag.total_estimated_risk = sum(n.estimated_risk for n in dag.nodes.values())

        return dag

    def plan_single(self, envelope: ExecutionEnvelope) -> ExecutionDAG:
        """Plan execution for a single action."""
        return self.plan([envelope])

    def _infer_dependencies(
        self, dag: ExecutionDAG, envelopes: list[ExecutionEnvelope]
    ) -> None:
        """Infer data-flow dependencies between actions."""
        # Map resources to their writers/readers
        resource_writers: dict[str, list[str]] = defaultdict(list)

        for env in envelopes:
            for target in env.resource_targets:
                if env.intent.action_type.value in ("write", "delete", "execute"):
                    resource_writers[target].append(env.action_id)

        # Actions that read from a resource depend on prior writers
        for env in envelopes:
            for target in env.resource_targets:
                writers = resource_writers.get(target, [])
                for writer_id in writers:
                    if writer_id != env.action_id:
                        dag.edges.append((writer_id, env.action_id))
                        if writer_id not in dag.nodes[env.action_id].dependencies:
                            dag.nodes[env.action_id].dependencies.append(writer_id)

    def _detect_cycles(self, dag: ExecutionDAG) -> bool:
        """Detect if the DAG contains cycles using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in dag.nodes}
        adj = defaultdict(list)
        for u, v in dag.edges:
            adj[u].append(v)

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adj[node]:
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        return any(
            dfs(nid) for nid in dag.nodes if color.get(nid) == WHITE
        )

    def _find_cycles(self, dag: ExecutionDAG) -> list[list[str]]:
        """Find all cycles in the graph."""
        cycles: list[list[str]] = []
        adj = defaultdict(list)
        for u, v in dag.edges:
            adj[u].append(v)

        visited = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> None:
            if node in path_set:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in adj[node]:
                dfs(neighbor)
            path.pop()
            path_set.discard(node)

        for nid in dag.nodes:
            dfs(nid)

        return cycles

    def _topological_sort(self, dag: ExecutionDAG) -> list[str]:
        """Kahn's algorithm for topological ordering."""
        in_degree: dict[str, int] = {nid: 0 for nid in dag.nodes}
        adj = defaultdict(list)
        for u, v in dag.edges:
            adj[u].append(v)
            if v in in_degree:
                in_degree[v] += 1

        queue = deque(nid for nid, d in in_degree.items() if d == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        return order

    def _compute_critical_path(self, dag: ExecutionDAG) -> list[str]:
        """Find the longest path through the DAG (critical path)."""
        if dag.has_cycles or not dag.execution_order:
            return list(dag.nodes.keys())

        adj = defaultdict(list)
        for u, v in dag.edges:
            adj[u].append(v)

        dist: dict[str, int] = {nid: 0 for nid in dag.nodes}
        parent: dict[str, str] = {}

        for node in dag.execution_order:
            for neighbor in adj[node]:
                if neighbor in dist and dist[node] + 1 > dist[neighbor]:
                    dist[neighbor] = dist[node] + 1
                    parent[neighbor] = node

        if not dist:
            return []

        end_node = max(dist, key=lambda k: dist[k])
        path = [end_node]
        while end_node in parent:
            end_node = parent[end_node]
            path.append(end_node)
        path.reverse()
        return path

    def _annotate_state_hashes(
        self, dag: ExecutionDAG, envelopes: list[ExecutionEnvelope]
    ) -> None:
        """Predict state hashes for each node."""
        env_map = {e.action_id: e for e in envelopes}
        cumulative_state: dict[str, Any] = {}

        for node_id in (dag.execution_order or list(dag.nodes.keys())):
            node = dag.nodes[node_id]
            env = env_map.get(node_id)
            if not env:
                continue

            # Pre-state is current cumulative state
            pre_canonical = json.dumps(cumulative_state, sort_keys=True)
            node.predicted_pre_hash = hashlib.sha256(pre_canonical.encode()).hexdigest()

            # Predict post-state changes
            for change in env.intent.expected_state_changes:
                cumulative_state[f"{node_id}:{change}"] = True

            post_canonical = json.dumps(cumulative_state, sort_keys=True)
            node.predicted_post_hash = hashlib.sha256(post_canonical.encode()).hexdigest()
