"""
Infrastructure Mutation Plugin — detects dangerous infra changes.

Simulates risks of modifying cloud resources, containers, databases,
networking configs, and deployment pipelines.
"""

from __future__ import annotations

import re

from agent_preflight.atf.models import ActionEnvelope, DomainSimulationResult
from agent_preflight.atf.simulation import SimulationPlugin

_INFRA_PATTERNS = re.compile(
    r"(deploy|terraform|ansible|kubernetes|k8s|docker|helm|"
    r"cloudformation|pulumi|aws|gcp|azure|"
    r"database|migrate|schema|alter|drop|"
    r"firewall|security.?group|iam|permission|role|"
    r"dns|route|load.?balancer|cert|ssl|tls)",
    re.IGNORECASE,
)
_DESTRUCTIVE_INFRA = re.compile(
    r"(destroy|terminate|delete|decommission|rollback|downgrade|scale.?down)",
    re.IGNORECASE,
)


class InfrastructureMutationPlugin(SimulationPlugin):
    """Simulates infrastructure mutation risks."""

    @property
    def name(self) -> str:
        return "infrastructure_mutation"

    def supports(self, envelope: ActionEnvelope) -> bool:
        combined = envelope.tool_name + " " + str(envelope.arguments)
        return bool(_INFRA_PATTERNS.search(combined))

    async def simulate(
        self, envelope: ActionEnvelope, perturbation: dict[str, float]
    ) -> DomainSimulationResult:
        combined = envelope.tool_name + " " + str(envelope.arguments)
        failure = False
        cascade = False
        impact = 0.0
        details: dict = {}

        # Infrastructure changes are inherently high-impact
        impact = 0.5
        cascade = True

        # Destructive infra operations
        if _DESTRUCTIVE_INFRA.search(combined):
            impact = 0.9
            if perturbation.get("external_failure_prob", 0) > 0.1:
                failure = True
                details["reason"] = "destructive_infra_with_external_failure"

        # Under high concurrent load, infra changes are dangerous
        if perturbation.get("concurrent_load", 0) > 0.7:
            failure = True
            details["reason"] = "infra_change_during_peak_load"
            impact = max(impact, 0.8)

        # Network latency can cause partial deployments
        if perturbation.get("network_latency_ms", 50) > 300:
            if "deploy" in combined.lower():
                failure = True
                details["reason"] = "deployment_timeout_partial_rollout"
                cascade = True
                impact = max(impact, 0.9)

        return DomainSimulationResult(
            plugin_name=self.name,
            failure_detected=failure,
            failure_description=details.get("reason", ""),
            cascade_detected=cascade,
            resource_impact=impact,
            details=details,
        )
