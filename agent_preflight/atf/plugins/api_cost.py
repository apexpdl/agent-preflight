"""
API Cost Explosion Plugin — detects potential cost spikes from API calls.

Simulates scenarios where API costs spiral due to retries, pagination
loops, rate-limit backoff storms, or unbounded batch operations.
"""

from __future__ import annotations

import re

from agent_preflight.atf.models import ActionEnvelope, DomainSimulationResult
from agent_preflight.atf.simulation import SimulationPlugin

_API_PATTERNS = re.compile(
    r"(api|http|request|fetch|call|invoke|endpoint|webhook|rest|graphql)",
    re.IGNORECASE,
)
_BATCH_PATTERNS = re.compile(
    r"(batch|bulk|all|foreach|map|loop|iterate|paginate)", re.IGNORECASE
)


class APICostExplosionPlugin(SimulationPlugin):
    """Simulates API cost explosion under perturbation."""

    @property
    def name(self) -> str:
        return "api_cost_explosion"

    def supports(self, envelope: ActionEnvelope) -> bool:
        tool_lower = envelope.tool_name.lower()
        return bool(_API_PATTERNS.search(tool_lower) or envelope.intent.external_calls)

    async def simulate(
        self, envelope: ActionEnvelope, perturbation: dict[str, float]
    ) -> DomainSimulationResult:
        base_cost = envelope.intent.estimated_cost
        failure = False
        details: dict = {}
        impact = 0.0

        # Rate limit proximity can cause retry storms
        rate_limit = perturbation.get("api_rate_limit_proximity", 0)
        if rate_limit > 0.7:
            retry_multiplier = 1 + (rate_limit * 5)
            simulated_cost = base_cost * retry_multiplier
            if simulated_cost > base_cost * 3:
                failure = True
                details["reason"] = "retry_storm"
                details["simulated_cost"] = round(simulated_cost, 2)
                impact = min(simulated_cost / 500, 1.0)

        # Batch operations under load can explode
        args_str = str(envelope.arguments)
        if _BATCH_PATTERNS.search(args_str):
            load = perturbation.get("concurrent_load", 0)
            if load > 0.6:
                failure = True
                details["reason"] = "batch_under_high_load"
                impact = max(impact, 0.6)

        # Network latency can cause timeout retries
        latency = perturbation.get("network_latency_ms", 50)
        if latency > 200 and base_cost > 1.0:
            if perturbation.get("external_failure_prob", 0) > 0.1:
                failure = True
                details["reason"] = "timeout_retry_cost_amplification"
                impact = max(impact, 0.5)

        return DomainSimulationResult(
            plugin_name=self.name,
            failure_detected=failure,
            failure_description=details.get("reason", ""),
            cascade_detected=False,
            resource_impact=impact,
            details=details,
        )
