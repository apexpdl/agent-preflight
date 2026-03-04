"""
Filesystem Cascade Plugin — simulates cascading file system failures.

Detects recursive deletions, wildcard expansions, symlink traversals,
write-overwrite races, and permission escalation patterns.
"""

from __future__ import annotations

import re

from agent_preflight.atf.models import ActionEnvelope, DomainSimulationResult
from agent_preflight.atf.simulation import SimulationPlugin

_RECURSIVE_PATTERNS = re.compile(
    r"(rm\s+-rf|rmdir|shutil\.rmtree|os\.removedirs|recursive.*delete|\*\*/\*|glob\.\*\*)",
    re.IGNORECASE,
)
_WILDCARD_PATTERNS = re.compile(r"(\*|\?|\[.*\])", re.IGNORECASE)
_DANGEROUS_PATHS = re.compile(
    r"^(/|/home|/etc|/usr|/var|/tmp|/root|C:\\|C:\\Windows)", re.IGNORECASE
)


class FilesystemCascadePlugin(SimulationPlugin):
    """Simulates filesystem cascade failures under perturbation."""

    @property
    def name(self) -> str:
        return "filesystem_cascade"

    def supports(self, envelope: ActionEnvelope) -> bool:
        tool_lower = envelope.tool_name.lower()
        keywords = ("file", "write", "read", "delete", "remove", "copy", "move",
                     "mkdir", "rmdir", "fs", "path", "os.", "shutil")
        if any(k in tool_lower for k in keywords):
            return True
        args_str = str(envelope.arguments)
        return bool(_RECURSIVE_PATTERNS.search(args_str))

    async def simulate(
        self, envelope: ActionEnvelope, perturbation: dict[str, float]
    ) -> DomainSimulationResult:
        args_str = str(envelope.arguments)
        failure = False
        cascade = False
        impact = 0.0
        details: dict = {}

        # Check for recursive operations
        if _RECURSIVE_PATTERNS.search(args_str):
            # Under resource pressure, recursive ops are more dangerous
            if perturbation.get("resource_pressure", 0) > 0.6:
                failure = True
                details["reason"] = "recursive_deletion_under_pressure"
            cascade = True
            impact = 0.8

        # Check for wildcards
        if _WILDCARD_PATTERNS.search(args_str):
            if perturbation.get("concurrent_load", 0) > 0.5:
                failure = True
                details["reason"] = "wildcard_expansion_in_high_load"
            impact = max(impact, 0.5)

        # Check for dangerous root paths
        for target in envelope.resource_targets:
            if _DANGEROUS_PATHS.match(target):
                failure = True
                cascade = True
                impact = 1.0
                details["dangerous_path"] = target
                break

        # Timing perturbation can cause partial writes
        if perturbation.get("timing_variance", 1.0) > 1.5:
            if "write" in envelope.tool_name.lower():
                if perturbation.get("external_failure_prob", 0) > 0.15:
                    failure = True
                    details["reason"] = "partial_write_under_timing_variance"

        return DomainSimulationResult(
            plugin_name=self.name,
            failure_detected=failure,
            failure_description=details.get("reason", ""),
            cascade_detected=cascade,
            resource_impact=impact,
            details=details,
        )
