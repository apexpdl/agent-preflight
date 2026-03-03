"""Core data models for agent-preflight."""

from __future__ import annotations

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

        return self

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

    def to_dict(self) -> dict:
        return {
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

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
