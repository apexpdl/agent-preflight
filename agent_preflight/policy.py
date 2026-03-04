"""
Policy engine for agent-preflight.

Declarative rules that evaluate plans and enforce organizational policies.
Think of it like OPA (Open Policy Agent) but for AI agent actions.

Example:
    engine = PolicyEngine()
    engine.add(Policy.deny("No critical actions").when(risk_level=RiskLevel.CRITICAL))
    engine.add(Policy.deny("No drops").when_args_match(r"DROP TABLE"))
    engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))
    engine.add(Policy.budget_limit("Stay under $10", max_cost=10.0))

    result = engine.evaluate(plan)
    if result.blocked:
        print(result.summary())
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .models import ActionCapture, Plan, RiskLevel, ActionType, Reversibility


class PolicyVerdict(Enum):
    """Result of a policy evaluation."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    WARN = "WARN"


@dataclass
class PolicyViolation:
    """A single policy violation."""
    policy_name: str
    verdict: PolicyVerdict
    reason: str
    action: Optional[ActionCapture] = None
    details: str = ""


@dataclass
class PolicyResult:
    """Aggregate result of evaluating all policies against a plan."""
    violations: list[PolicyViolation] = field(default_factory=list)
    passed: int = 0
    total_policies: int = 0

    @property
    def blocked(self) -> bool:
        return any(v.verdict == PolicyVerdict.DENY for v in self.violations)

    @property
    def needs_approval(self) -> bool:
        return any(v.verdict == PolicyVerdict.REQUIRE_APPROVAL for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.verdict == PolicyVerdict.WARN for v in self.violations)

    @property
    def clean(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        lines = []
        if self.blocked:
            denials = [v for v in self.violations if v.verdict == PolicyVerdict.DENY]
            lines.append(f"BLOCKED: {len(denials)} policy violation(s)")
            for v in denials:
                action_info = f" on '{v.action.name}'" if v.action else ""
                lines.append(f"  DENY: {v.policy_name}{action_info} - {v.reason}")
                if v.details:
                    lines.append(f"    {v.details}")

        approvals = [v for v in self.violations if v.verdict == PolicyVerdict.REQUIRE_APPROVAL]
        if approvals:
            lines.append(f"APPROVAL REQUIRED: {len(approvals)} action(s)")
            for v in approvals:
                action_info = f" on '{v.action.name}'" if v.action else ""
                lines.append(f"  REVIEW: {v.policy_name}{action_info} - {v.reason}")

        warnings = [v for v in self.violations if v.verdict == PolicyVerdict.WARN]
        if warnings:
            lines.append(f"WARNINGS: {len(warnings)}")
            for v in warnings:
                action_info = f" on '{v.action.name}'" if v.action else ""
                lines.append(f"  WARN: {v.policy_name}{action_info} - {v.reason}")

        if not lines:
            lines.append(f"ALL CLEAR: {self.passed}/{self.total_policies} policies passed")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "needs_approval": self.needs_approval,
            "passed": self.passed,
            "total_policies": self.total_policies,
            "violations": [
                {
                    "policy": v.policy_name,
                    "verdict": v.verdict.value,
                    "reason": v.reason,
                    "action": v.action.name if v.action else None,
                    "details": v.details,
                }
                for v in self.violations
            ],
        }


class Policy:
    """
    A single policy rule with a fluent builder API.

    Usage:
        Policy.deny("No financial ops").when(risk_level=RiskLevel.CRITICAL)
        Policy.deny("No drops").when_args_match(r"DROP TABLE")
        Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE)
        Policy.budget_limit("Budget cap", max_cost=50.0)
        Policy.max_actions("Too many actions", limit=20)
        Policy.deny("No prod").when_custom(lambda a: "prod" in str(a.args))
    """

    def __init__(self, name: str, verdict: PolicyVerdict):
        self.name = name
        self.verdict = verdict
        self._conditions: list[Callable[[ActionCapture], bool]] = []
        self._plan_conditions: list[Callable[[Plan], Optional[str]]] = []
        self._reason = ""

    @classmethod
    def deny(cls, name: str) -> "Policy":
        return cls(name, PolicyVerdict.DENY)

    @classmethod
    def warn(cls, name: str) -> "Policy":
        return cls(name, PolicyVerdict.WARN)

    @classmethod
    def require_approval(cls, name: str) -> "Policy":
        return cls(name, PolicyVerdict.REQUIRE_APPROVAL)

    @classmethod
    def budget_limit(cls, name: str, max_cost: float) -> "Policy":
        """Deny if total plan cost exceeds max_cost."""
        p = cls(name, PolicyVerdict.DENY)
        p._reason = f"Total cost exceeds ${max_cost:.2f}"

        def check_budget(plan: Plan) -> Optional[str]:
            if plan.total_estimated_cost > max_cost:
                return f"Plan cost ${plan.total_estimated_cost:.2f} exceeds limit ${max_cost:.2f}"
            return None

        p._plan_conditions.append(check_budget)
        return p

    @classmethod
    def max_actions(cls, name: str, limit: int) -> "Policy":
        """Deny if plan has more than `limit` actions."""
        p = cls(name, PolicyVerdict.DENY)
        p._reason = f"Too many actions (limit: {limit})"

        def check_count(plan: Plan) -> Optional[str]:
            if len(plan.actions) > limit:
                return f"Plan has {len(plan.actions)} actions, limit is {limit}"
            return None

        p._plan_conditions.append(check_count)
        return p

    @classmethod
    def no_irreversible(cls, name: str = "No irreversible actions") -> "Policy":
        """Deny any irreversible actions."""
        p = cls(name, PolicyVerdict.DENY)
        p._reason = "Irreversible action detected"
        p._conditions.append(
            lambda a: a.reversibility == Reversibility.IRREVERSIBLE
        )
        return p

    def when(self, **kwargs: Any) -> "Policy":
        """
        Match actions by attribute values.

        Supports: risk_level, action_type, reversibility, name
        """
        for attr, value in kwargs.items():
            if attr == "name":
                pattern = re.compile(value, re.IGNORECASE) if isinstance(value, str) else value
                self._conditions.append(lambda a, p=pattern: bool(p.search(a.name)))
                self._reason = self._reason or f"Action name matches '{value}'"
            else:
                self._conditions.append(lambda a, k=attr, v=value: getattr(a, k, None) == v)
                self._reason = self._reason or f"{attr} == {value}"
        return self

    def when_args_match(self, pattern: str) -> "Policy":
        """Match actions whose arguments contain the given regex pattern."""
        compiled = re.compile(pattern, re.IGNORECASE)
        self._reason = self._reason or f"Arguments match '{pattern}'"

        def check(action: ActionCapture) -> bool:
            text = " ".join(str(v) for v in action.args.values())
            text += " " + " ".join(str(v) for v in action.kwargs.values())
            return bool(compiled.search(text))

        self._conditions.append(check)
        return self

    def when_custom(self, fn: Callable[[ActionCapture], bool]) -> "Policy":
        """Match actions using a custom predicate function."""
        self._reason = self._reason or "Custom condition matched"
        self._conditions.append(fn)
        return self

    def reason(self, text: str) -> "Policy":
        """Set a custom reason message."""
        self._reason = text
        return self

    def evaluate(self, plan: Plan) -> list[PolicyViolation]:
        """Evaluate this policy against a plan. Returns violations."""
        violations = []

        # Plan-level conditions
        for check in self._plan_conditions:
            detail = check(plan)
            if detail:
                violations.append(PolicyViolation(
                    policy_name=self.name,
                    verdict=self.verdict,
                    reason=self._reason,
                    details=detail,
                ))

        # Action-level conditions
        if self._conditions:
            for action in plan.actions:
                if all(cond(action) for cond in self._conditions):
                    violations.append(PolicyViolation(
                        policy_name=self.name,
                        verdict=self.verdict,
                        reason=self._reason,
                        action=action,
                    ))

        return violations


class PolicyEngine:
    """
    Evaluates a collection of policies against a plan.

    Usage:
        engine = PolicyEngine()
        engine.add(Policy.deny("Block critical").when(risk_level=RiskLevel.CRITICAL))
        engine.add(Policy.budget_limit("Budget", max_cost=50.0))

        result = engine.evaluate(plan)
        if result.blocked:
            print(result.summary())
            sys.exit(1)
    """

    def __init__(self) -> None:
        self._policies: list[Policy] = []

    def add(self, policy: Policy) -> "PolicyEngine":
        """Add a policy to the engine."""
        self._policies.append(policy)
        return self

    def evaluate(self, plan: Plan) -> PolicyResult:
        """Evaluate all policies against a plan."""
        result = PolicyResult(total_policies=len(self._policies))

        for policy in self._policies:
            violations = policy.evaluate(plan)
            if violations:
                result.violations.extend(violations)
            else:
                result.passed += 1

        return result

    def __len__(self) -> int:
        return len(self._policies)
