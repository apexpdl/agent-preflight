"""
Probabilistic Simulation Engine — Monte Carlo consequence modeling.

Runs N lightweight rollouts with perturbations to estimate
failure probability, cascade risk, and volatility for actions
that pass structural risk checks but need deeper analysis.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from agent_preflight.atf.models import (
    ActionEnvelope,
    DomainSimulationResult,
    SimulationResult,
)


# ---------------------------------------------------------------------------
# Plugin Interface
# ---------------------------------------------------------------------------

class SimulationPlugin(ABC):
    """Base class for domain-specific simulation plugins.

    Plugins are independently installable and can be contributed by
    third parties. Each plugin handles a specific domain of risk.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier."""

    @abstractmethod
    def supports(self, envelope: ActionEnvelope) -> bool:
        """Return True if this plugin can simulate the given action."""

    @abstractmethod
    async def simulate(
        self,
        envelope: ActionEnvelope,
        perturbation: dict[str, float],
    ) -> DomainSimulationResult:
        """Run a single simulation rollout with given perturbations."""


# ---------------------------------------------------------------------------
# Built-in Perturbation Generator
# ---------------------------------------------------------------------------

class PerturbationGenerator:
    """Generates randomized perturbation vectors for rollouts.

    Each perturbation represents a slightly different execution
    environment: timing variance, resource pressure, network issues, etc.
    """

    @staticmethod
    def generate(seed: Optional[int] = None) -> dict[str, float]:
        rng = random.Random(seed)
        return {
            "timing_variance": rng.gauss(1.0, 0.3),
            "resource_pressure": rng.uniform(0.0, 1.0),
            "network_latency_ms": max(0, rng.gauss(50, 100)),
            "memory_pressure": rng.uniform(0.0, 1.0),
            "api_rate_limit_proximity": rng.uniform(0.0, 1.0),
            "external_failure_prob": rng.uniform(0.0, 0.3),
            "concurrent_load": rng.uniform(0.0, 1.0),
        }


# ---------------------------------------------------------------------------
# Simulation Engine
# ---------------------------------------------------------------------------

class SimulationEngine:
    """Orchestrates Monte Carlo rollouts across registered plugins.

    For each rollout:
    1. Generate perturbation vector
    2. Run all applicable plugins with that perturbation
    3. Aggregate domain results

    After N rollouts, compute statistical summary.
    """

    def __init__(self):
        self._plugins: list[SimulationPlugin] = []

    def register_plugin(self, plugin: SimulationPlugin) -> None:
        """Register a simulation plugin."""
        self._plugins.append(plugin)

    async def run_rollouts(
        self,
        envelope: ActionEnvelope,
        n: int = 50,
        max_concurrent: int = 10,
    ) -> SimulationResult:
        """Run N simulation rollouts and aggregate results."""
        start = time.perf_counter()

        # Find applicable plugins
        applicable = [p for p in self._plugins if p.supports(envelope)]
        if not applicable:
            return SimulationResult(
                rollout_count=0,
                total_time_ms=0,
                confidence_interval=(0.0, 0.0),
            )

        # Run rollouts with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        all_results: list[list[DomainSimulationResult]] = []

        async def single_rollout(seed: int) -> list[DomainSimulationResult]:
            async with semaphore:
                perturbation = PerturbationGenerator.generate(seed)
                results = []
                for plugin in applicable:
                    result = await plugin.simulate(envelope, perturbation)
                    results.append(result)
                return results

        tasks = [single_rollout(i) for i in range(n)]
        all_results = await asyncio.gather(*tasks)

        # Aggregate statistics
        failures = 0
        cascades = 0
        resource_spikes = 0
        all_domain_results: list[DomainSimulationResult] = []

        for rollout_results in all_results:
            rollout_failed = False
            rollout_cascade = False
            rollout_spike = False
            for dr in rollout_results:
                all_domain_results.append(dr)
                if dr.failure_detected:
                    rollout_failed = True
                if dr.cascade_detected:
                    rollout_cascade = True
                if dr.resource_impact > 0.7:
                    rollout_spike = True
            if rollout_failed:
                failures += 1
            if rollout_cascade:
                cascades += 1
            if rollout_spike:
                resource_spikes += 1

        failure_prob = failures / n
        cascade_prob = cascades / n
        spike_prob = resource_spikes / n

        # Compute volatility (variance in failure rates)
        failure_rates_per_plugin: dict[str, list[float]] = {}
        for dr in all_domain_results:
            failure_rates_per_plugin.setdefault(dr.plugin_name, []).append(
                1.0 if dr.failure_detected else 0.0
            )
        volatilities = []
        for rates in failure_rates_per_plugin.values():
            if len(rates) > 1:
                mean = sum(rates) / len(rates)
                variance = sum((r - mean) ** 2 for r in rates) / len(rates)
                volatilities.append(math.sqrt(variance))
        volatility = max(volatilities) if volatilities else 0.0

        # Wilson score confidence interval for failure probability
        ci = _wilson_ci(failures, n)

        elapsed = (time.perf_counter() - start) * 1000

        # Deduplicate domain results for summary (keep unique plugin results)
        unique_domain: list[DomainSimulationResult] = []
        seen_plugins: set[str] = set()
        for dr in all_domain_results:
            if dr.plugin_name not in seen_plugins and dr.failure_detected:
                unique_domain.append(dr)
                seen_plugins.add(dr.plugin_name)

        return SimulationResult(
            failure_probability=round(failure_prob, 4),
            cascade_probability=round(cascade_prob, 4),
            resource_spike_probability=round(spike_prob, 4),
            volatility_score=round(volatility, 4),
            confidence_interval=(round(ci[0], 4), round(ci[1], 4)),
            rollout_count=n,
            domain_results=unique_domain,
            total_time_ms=round(elapsed, 3),
        )


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p_hat = successes / n
    denominator = 1 + z * z / n
    centre = p_hat + z * z / (2 * n)
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * n)) / n)
    lower = max(0.0, (centre - spread) / denominator)
    upper = min(1.0, (centre + spread) / denominator)
    return (lower, upper)
