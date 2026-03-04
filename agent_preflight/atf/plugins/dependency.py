"""
Dependency Graph Plugin — detects dependency breakage risks.

Simulates scenarios where modifying shared resources, config files,
or package dependencies causes cascading breakage downstream.
"""

from __future__ import annotations

import re

from agent_preflight.atf.models import ActionEnvelope, DomainSimulationResult
from agent_preflight.atf.simulation import SimulationPlugin

_DEP_FILES = re.compile(
    r"(requirements\.txt|package\.json|Gemfile|go\.mod|Cargo\.toml|"
    r"pyproject\.toml|setup\.py|pom\.xml|build\.gradle|Makefile|Dockerfile|"
    r"docker-compose|\.lock|yarn\.lock|poetry\.lock)",
    re.IGNORECASE,
)
_CONFIG_FILES = re.compile(
    r"(\.(yaml|yml|json|toml|ini|cfg|conf|env)|config|settings)", re.IGNORECASE
)
_SHARED_PATTERNS = re.compile(
    r"(shared|common|core|base|lib|util|framework|infrastructure)", re.IGNORECASE
)


class DependencyGraphPlugin(SimulationPlugin):
    """Simulates dependency graph breakage under perturbation."""

    @property
    def name(self) -> str:
        return "dependency_graph"

    def supports(self, envelope: ActionEnvelope) -> bool:
        args_str = str(envelope.arguments) + " ".join(envelope.resource_targets)
        return bool(
            _DEP_FILES.search(args_str)
            or _CONFIG_FILES.search(args_str)
            or _SHARED_PATTERNS.search(args_str)
        )

    async def simulate(
        self, envelope: ActionEnvelope, perturbation: dict[str, float]
    ) -> DomainSimulationResult:
        args_str = str(envelope.arguments) + " ".join(envelope.resource_targets)
        failure = False
        cascade = False
        impact = 0.0
        details: dict = {}

        # Modifying dependency files is inherently risky
        if _DEP_FILES.search(args_str):
            cascade = True
            impact = 0.6
            # Under timing variance, partial updates cause inconsistency
            if perturbation.get("timing_variance", 1.0) > 1.3:
                failure = True
                details["reason"] = "partial_dependency_update"

        # Config changes cascade through systems
        if _CONFIG_FILES.search(args_str):
            if perturbation.get("concurrent_load", 0) > 0.5:
                cascade = True
                impact = max(impact, 0.5)
                if perturbation.get("external_failure_prob", 0) > 0.15:
                    failure = True
                    details["reason"] = "config_change_during_high_load"

        # Shared/core module changes have wide blast radius
        if _SHARED_PATTERNS.search(args_str):
            cascade = True
            impact = max(impact, 0.7)
            if perturbation.get("resource_pressure", 0) > 0.5:
                failure = True
                details["reason"] = "shared_module_change_under_pressure"

        return DomainSimulationResult(
            plugin_name=self.name,
            failure_detected=failure,
            failure_description=details.get("reason", ""),
            cascade_detected=cascade,
            resource_impact=impact,
            details=details,
        )
