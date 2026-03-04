"""Core data models for agent-preflight."""

from __future__ import annotations

import asyncio
import time
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, Callable


class RiskLevel(Enum):
    """Risk classification for an action."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(Enum):
    """Whether an action reads or writes."""
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class Reversibility(Enum):
    """Whether an action can be undone."""
    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class ActionCapture:
    """A single captured agent action (tool call)."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    kwargs: dict[str, Any] = field(default_factory=dict)

    # Classification (filled by classifiers)
    action_type: ActionType = ActionType.EXECUTE
    reversibility: Reversibility = Reversibility.UNKNOWN
    risk_level: RiskLevel = RiskLevel.MEDIUM
    estimated_cost: Optional[float] = None
    risk_reasons: list[str] = field(default_factory=list)

    # Dependency tracking
    depends_on: list[int] = field(default_factory=list)  # sequence numbers
    output_key: Optional[str] = None  # label for this action's output

    # Metadata
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        d["reversibility"] = self.reversibility.value
        d["risk_level"] = self.risk_level.value
        return d


@dataclass
class DependencyGraph:
    """Tracks dependencies between actions in a plan."""

    edges: dict[int, list[int]] = field(default_factory=dict)  # action -> depends_on
    _actions: dict[int, ActionCapture] = field(default_factory=dict)

    @classmethod
    def from_actions(cls, actions: list[ActionCapture]) -> "DependencyGraph":
        """
        Build a dependency graph by analyzing data flow between actions.

        Heuristic: if action B's arguments reference action A's name or output,
        B depends on A. Also, writes before deletes on the same resource create
        implicit dependencies.
        """
        graph = cls()
        resources_written: dict[str, list[int]] = {}  # resource -> [sequences]

        for action in actions:
            graph._actions[action.sequence] = action
            graph.edges[action.sequence] = list(action.depends_on)

            # Track resource access patterns
            all_args_text = " ".join(str(v) for v in action.args.values())
            all_args_text += " " + " ".join(str(v) for v in action.kwargs.values())

            # If this action references a resource that was written to earlier,
            # create an implicit dependency
            for resource, writers in resources_written.items():
                if resource in all_args_text and writers:
                    for writer_seq in writers:
                        if writer_seq not in graph.edges[action.sequence]:
                            graph.edges[action.sequence].append(writer_seq)

            # Track writes/deletes for dependency inference
            if action.action_type in (ActionType.WRITE, ActionType.DELETE):
                for v in action.args.values():
                    key = str(v)
                    if key:
                        resources_written.setdefault(key, []).append(action.sequence)

        return graph

    @property
    def execution_order(self) -> list[int]:
        """Topological sort - returns action sequences in safe execution order."""
        visited: set[int] = set()
        order: list[int] = []

        def visit(seq: int) -> None:
            if seq in visited:
                return
            visited.add(seq)
            for dep in self.edges.get(seq, []):
                visit(dep)
            order.append(seq)

        for seq in sorted(self.edges.keys()):
            visit(seq)

        return order

    @property
    def has_cycles(self) -> bool:
        """Check for circular dependencies."""
        in_progress: set[int] = set()
        visited: set[int] = set()

        def has_cycle(seq: int) -> bool:
            if seq in in_progress:
                return True
            if seq in visited:
                return False
            in_progress.add(seq)
            for dep in self.edges.get(seq, []):
                if has_cycle(dep):
                    return True
            in_progress.discard(seq)
            visited.add(seq)
            return False

        return any(has_cycle(seq) for seq in self.edges)

    @property
    def critical_path(self) -> list[int]:
        """
        Find the longest dependency chain (most actions that must run sequentially).
        """
        memo: dict[int, int] = {}

        def depth(seq: int) -> int:
            if seq in memo:
                return memo[seq]
            deps = self.edges.get(seq, [])
            d = 1 + max((depth(d) for d in deps), default=0)
            memo[seq] = d
            return d

        if not self.edges:
            return []

        deepest = max(self.edges.keys(), key=depth)

        # Reconstruct path
        path = [deepest]
        current = deepest
        while self.edges.get(current):
            deps = self.edges[current]
            current = max(deps, key=depth)
            path.append(current)
        path.reverse()
        return path

    def to_dict(self) -> dict:
        return {
            "edges": {str(k): v for k, v in self.edges.items()},
            "execution_order": self.execution_order,
            "has_cycles": self.has_cycles,
            "critical_path_length": len(self.critical_path),
        }


@dataclass
class Plan:
    """A preflight plan showing all captured actions."""

    actions: list[ActionCapture] = field(default_factory=list)
    task_description: str = ""
    created_at: float = field(default_factory=time.time)

    # Computed on finalize
    total_estimated_cost: float = 0.0
    overall_risk: RiskLevel = RiskLevel.LOW
    irreversible_count: int = 0
    warnings: list[str] = field(default_factory=list)
    dependency_graph: Optional[DependencyGraph] = field(default=None, repr=False)

    # Execution
    _executors: dict[str, Callable] = field(default_factory=dict, repr=False)
    _approved: bool = False

    def finalize(self) -> "Plan":
        """Compute summary stats after all actions captured."""
        self.total_estimated_cost = sum(
            a.estimated_cost for a in self.actions if a.estimated_cost
        )
        self.irreversible_count = sum(
            1 for a in self.actions
            if a.reversibility == Reversibility.IRREVERSIBLE
        )

        # Determine overall risk
        if any(a.risk_level == RiskLevel.CRITICAL for a in self.actions):
            self.overall_risk = RiskLevel.CRITICAL
        elif any(a.risk_level == RiskLevel.HIGH for a in self.actions):
            self.overall_risk = RiskLevel.HIGH
        elif any(a.risk_level == RiskLevel.MEDIUM for a in self.actions):
            self.overall_risk = RiskLevel.MEDIUM
        else:
            self.overall_risk = RiskLevel.LOW

        # Detect loops
        name_counts: dict[str, int] = {}
        for a in self.actions:
            name_counts[a.name] = name_counts.get(a.name, 0) + 1
        for name, count in name_counts.items():
            if count >= 3:
                self.warnings.append(
                    f"LOOP DETECTED: '{name}' called {count} times"
                )
                self.overall_risk = RiskLevel.CRITICAL

        # Warn on irreversible actions
        if self.irreversible_count > 0:
            self.warnings.append(
                f"{self.irreversible_count} irreversible action(s) in plan"
            )

        # Warn on cost
        if self.total_estimated_cost > 1.0:
            self.warnings.append(
                f"Estimated cost: ${self.total_estimated_cost:.2f}"
            )

        # Build dependency graph
        self.dependency_graph = DependencyGraph.from_actions(self.actions)
        if self.dependency_graph.has_cycles:
            self.warnings.append("CIRCULAR DEPENDENCY detected in action chain")
            self.overall_risk = RiskLevel.CRITICAL

        # Detect dangerous patterns: delete without prior read
        self._check_delete_without_read()

        return self

    def _check_delete_without_read(self) -> None:
        """Warn if a DELETE action targets a resource that was never read first."""
        read_resources: set[str] = set()
        for action in self.actions:
            if action.action_type == ActionType.READ:
                for v in action.args.values():
                    read_resources.add(str(v))
            elif action.action_type == ActionType.DELETE:
                for v in action.args.values():
                    resource = str(v)
                    if resource and resource not in read_resources:
                        msg = f"DELETE on '{resource}' without prior READ - blind delete"
                        if msg not in self.warnings:
                            self.warnings.append(msg)

    def approve(self) -> "Plan":
        """Mark plan as approved for execution."""
        self._approved = True
        return self

    def execute(self) -> list[Any]:
        """Execute all actions in the plan. Must be approved first."""
        if not self._approved:
            raise RuntimeError(
                "Plan must be approved before execution. Call plan.approve() first."
            )
        results = []
        for action in self.actions:
            executor = self._executors.get(action.name)
            if executor is None:
                raise RuntimeError(f"No executor registered for '{action.name}'")
            result = executor(*action.args.values(), **action.kwargs)
            results.append(result)
        return results

    async def async_execute(self) -> list[Any]:
        """Execute all actions asynchronously. Must be approved first."""
        if not self._approved:
            raise RuntimeError(
                "Plan must be approved before execution. Call plan.approve() first."
            )
        results = []
        for action in self.actions:
            executor = self._executors.get(action.name)
            if executor is None:
                raise RuntimeError(f"No executor registered for '{action.name}'")
            if asyncio.iscoroutinefunction(executor):
                result = await executor(*action.args.values(), **action.kwargs)
            else:
                result = executor(*action.args.values(), **action.kwargs)
            results.append(result)
        return results

    def to_dict(self) -> dict:
        d = {
            "task": self.task_description,
            "actions": [a.to_dict() for a in self.actions],
            "summary": {
                "total_actions": len(self.actions),
                "estimated_cost": self.total_estimated_cost,
                "overall_risk": self.overall_risk.value,
                "irreversible_count": self.irreversible_count,
                "warnings": self.warnings,
            },
        }
        if self.dependency_graph:
            d["dependencies"] = self.dependency_graph.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
