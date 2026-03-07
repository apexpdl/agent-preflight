"""
TrustKernel Cost Governor.

Tracks token consumption, API calls, recursion depth, and tool
invocation caps. Enforces hard limits to prevent runaway cost
or infinite loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from trust_kernel.models import CostBudget, ExecutionEnvelope


@dataclass
class CostAlert:
    """Alert issued when approaching or exceeding budget limits."""
    alert_type: str  # warning, exceeded, blocked
    metric: str  # cost, tokens, api_calls, recursion, tool_invocations
    current_value: float = 0.0
    limit_value: float = 0.0
    message: str = ""


class CostGovernor:
    """Enforces cost and resource limits on AI agent actions.

    Tracks:
    - Financial cost (USD)
    - Token consumption
    - API call count
    - Recursion depth
    - Tool invocation count
    """

    def __init__(
        self,
        budget: Optional[CostBudget] = None,
        warning_threshold: float = 0.8,
    ):
        self._budget = budget or CostBudget()
        self._warning_threshold = warning_threshold
        self._recursion_stack: dict[str, int] = {}
        self._alerts: list[CostAlert] = []

    @property
    def budget(self) -> CostBudget:
        return self._budget

    @property
    def alerts(self) -> list[CostAlert]:
        return list(self._alerts)

    def can_execute(self, envelope: ExecutionEnvelope) -> tuple[bool, list[CostAlert]]:
        """Check if an action can execute within budget constraints."""
        alerts: list[CostAlert] = []
        can_proceed = True

        cost = envelope.intent.estimated_cost

        # Check financial cost
        if cost > 0:
            if not self._budget.can_afford(cost):
                alerts.append(CostAlert(
                    alert_type="blocked",
                    metric="cost",
                    current_value=self._budget.spent + cost,
                    limit_value=self._budget.total_budget,
                    message=f"Action cost ${cost:.2f} exceeds remaining budget "
                            f"${self._budget.remaining:.2f}",
                ))
                can_proceed = False
            elif (self._budget.spent + cost) / self._budget.total_budget > self._warning_threshold:
                alerts.append(CostAlert(
                    alert_type="warning",
                    metric="cost",
                    current_value=self._budget.spent + cost,
                    limit_value=self._budget.total_budget,
                    message=f"Budget usage at "
                            f"{(self._budget.spent + cost) / self._budget.total_budget:.0%}",
                ))

        # Check tool invocation limit
        if self._budget.tool_invocations_used >= self._budget.tool_invocation_limit:
            alerts.append(CostAlert(
                alert_type="blocked",
                metric="tool_invocations",
                current_value=self._budget.tool_invocations_used,
                limit_value=self._budget.tool_invocation_limit,
                message=f"Tool invocation limit reached: "
                        f"{self._budget.tool_invocations_used}/{self._budget.tool_invocation_limit}",
            ))
            can_proceed = False

        # Check API call limit
        if self._budget.api_calls_used >= self._budget.api_calls_limit:
            alerts.append(CostAlert(
                alert_type="blocked",
                metric="api_calls",
                current_value=self._budget.api_calls_used,
                limit_value=self._budget.api_calls_limit,
                message="API call limit reached",
            ))
            can_proceed = False

        # Check token budget
        if self._budget.tokens_used >= self._budget.token_budget:
            alerts.append(CostAlert(
                alert_type="blocked",
                metric="tokens",
                current_value=self._budget.tokens_used,
                limit_value=self._budget.token_budget,
                message="Token budget exhausted",
            ))
            can_proceed = False

        # Check recursion depth
        tool_depth = self._recursion_stack.get(envelope.tool_name, 0)
        if tool_depth >= self._budget.recursion_depth_limit:
            alerts.append(CostAlert(
                alert_type="blocked",
                metric="recursion",
                current_value=tool_depth,
                limit_value=self._budget.recursion_depth_limit,
                message=f"Recursion depth limit reached for {envelope.tool_name}",
            ))
            can_proceed = False

        self._alerts.extend(alerts)
        return can_proceed, alerts

    def charge(
        self,
        envelope: ExecutionEnvelope,
        tokens_used: int = 0,
    ) -> bool:
        """Charge the budget for an executed action."""
        cost = envelope.intent.estimated_cost
        success = self._budget.charge(cost, tokens_used)

        # Track recursion
        self._recursion_stack[envelope.tool_name] = (
            self._recursion_stack.get(envelope.tool_name, 0) + 1
        )

        return success

    def reset_recursion(self, tool_name: Optional[str] = None) -> None:
        """Reset recursion tracking."""
        if tool_name:
            self._recursion_stack.pop(tool_name, None)
        else:
            self._recursion_stack.clear()

    def get_usage_summary(self) -> dict[str, Any]:
        """Get a summary of current resource usage."""
        b = self._budget
        return {
            "cost": {
                "spent": b.spent,
                "remaining": b.remaining,
                "total": b.total_budget,
                "utilization": b.spent / max(b.total_budget, 0.01),
            },
            "tokens": {
                "used": b.tokens_used,
                "limit": b.token_budget,
                "utilization": b.tokens_used / max(b.token_budget, 1),
            },
            "api_calls": {
                "used": b.api_calls_used,
                "limit": b.api_calls_limit,
                "utilization": b.api_calls_used / max(b.api_calls_limit, 1),
            },
            "tool_invocations": {
                "used": b.tool_invocations_used,
                "limit": b.tool_invocation_limit,
                "utilization": b.tool_invocations_used / max(b.tool_invocation_limit, 1),
            },
            "active_alerts": len(self._alerts),
        }
