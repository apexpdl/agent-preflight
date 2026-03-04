"""
Memory Runaway Plugin — detects operations that could cause memory exhaustion.

Simulates scenarios involving large file reads, unbounded data loading,
recursive traversals, and memory-intensive transformations.
"""

from __future__ import annotations

import re

from agent_preflight.atf.models import ActionEnvelope, DomainSimulationResult
from agent_preflight.atf.simulation import SimulationPlugin

_MEMORY_PATTERNS = re.compile(
    r"(load_all|read_all|fetch_all|dump|export|collect|aggregate|"
    r"in_memory|buffer|cache_all|dataframe|pandas|numpy)",
    re.IGNORECASE,
)
_LARGE_DATA_PATTERNS = re.compile(
    r"(SELECT\s+\*|LIMIT\s+\d{5,}|no.?limit|unlimited|full.?scan|"
    r"\.csv|\.parquet|\.arrow|bulk)",
    re.IGNORECASE,
)


class MemoryRunawayPlugin(SimulationPlugin):
    """Simulates memory exhaustion scenarios."""

    @property
    def name(self) -> str:
        return "memory_runaway"

    def supports(self, envelope: ActionEnvelope) -> bool:
        combined = envelope.tool_name + " " + str(envelope.arguments)
        return bool(
            _MEMORY_PATTERNS.search(combined) or _LARGE_DATA_PATTERNS.search(combined)
        )

    async def simulate(
        self, envelope: ActionEnvelope, perturbation: dict[str, float]
    ) -> DomainSimulationResult:
        combined = envelope.tool_name + " " + str(envelope.arguments)
        failure = False
        details: dict = {}
        impact = 0.0

        memory_pressure = perturbation.get("memory_pressure", 0)

        # Large data operations under memory pressure
        if _LARGE_DATA_PATTERNS.search(combined):
            impact = 0.5
            if memory_pressure > 0.6:
                failure = True
                details["reason"] = "large_data_under_memory_pressure"
                impact = 0.9

        # Unbounded collection operations
        if _MEMORY_PATTERNS.search(combined):
            impact = max(impact, 0.4)
            if memory_pressure > 0.5 and perturbation.get("concurrent_load", 0) > 0.4:
                failure = True
                details["reason"] = "unbounded_collection_under_load"
                impact = max(impact, 0.8)

        return DomainSimulationResult(
            plugin_name=self.name,
            failure_detected=failure,
            failure_description=details.get("reason", ""),
            cascade_detected=False,
            resource_impact=impact,
            details=details,
        )
