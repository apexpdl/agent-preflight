"""
TrustKernel Reproducibility Engine.

Enables deterministic replay of any action using the same model
version, context, temperature, and state snapshot. Critical for
enterprise audits and incident investigation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from trust_kernel.models import (
    ExecutionEnvelope,
    ReplayManifest,
    StateSnapshot,
)


class ReproducibilityEngine:
    """Creates and validates deterministic replay manifests.

    Every action executed through TrustKernel can be replayed
    exactly by capturing:
    - Model version and seed
    - Temperature setting
    - Complete pre-state snapshot
    - Full execution envelope
    - Expected result for validation
    """

    def __init__(self):
        self._manifests: dict[str, ReplayManifest] = {}

    def create_manifest(
        self,
        envelope: ExecutionEnvelope,
        pre_state: StateSnapshot,
        model_version: str = "",
        model_seed: int = 0,
        temperature: float = 0.0,
        expected_result: Optional[dict[str, Any]] = None,
        dee_id: str = "",
    ) -> ReplayManifest:
        """Create a replay manifest capturing all execution context."""
        manifest = ReplayManifest(
            action_id=envelope.action_id,
            dee_id=dee_id,
            model_version=model_version,
            model_seed=model_seed,
            temperature=temperature,
            pre_state_snapshot=pre_state.entries,
            envelope_data={
                "agent_id": envelope.agent_id,
                "tool_name": envelope.tool_name,
                "arguments": envelope.arguments,
                "intent": {
                    "goal": envelope.intent.goal,
                    "reasoning_summary": envelope.intent.reasoning_summary,
                    "action_type": envelope.intent.action_type.value,
                    "reversible": envelope.intent.reversible,
                    "estimated_cost": envelope.intent.estimated_cost,
                    "confidence": envelope.intent.confidence,
                },
                "resource_targets": envelope.resource_targets,
            },
            expected_result=expected_result or {},
        )
        self._manifests[envelope.action_id] = manifest
        return manifest

    def validate_replay(
        self,
        manifest: ReplayManifest,
        actual_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate that a replay matches the expected result."""
        expected = manifest.expected_result
        if not expected:
            return {
                "valid": True,
                "reason": "No expected result to validate against",
                "manifest_id": manifest.manifest_id,
            }

        # Compare key fields
        mismatches: list[str] = []
        for key in expected:
            if key not in actual_result:
                mismatches.append(f"Missing key: {key}")
            elif expected[key] != actual_result.get(key):
                mismatches.append(
                    f"Mismatch on '{key}': expected={expected[key]}, "
                    f"actual={actual_result.get(key)}"
                )

        return {
            "valid": len(mismatches) == 0,
            "mismatches": mismatches,
            "manifest_id": manifest.manifest_id,
            "fidelity": 1.0 - (len(mismatches) / max(len(expected), 1)),
        }

    def get_manifest(self, action_id: str) -> Optional[ReplayManifest]:
        """Retrieve a replay manifest."""
        return self._manifests.get(action_id)

    def export_manifest(self, action_id: str) -> Optional[dict[str, Any]]:
        """Export a manifest as a portable dictionary."""
        manifest = self._manifests.get(action_id)
        if not manifest:
            return None
        return {
            "manifest_id": manifest.manifest_id,
            "action_id": manifest.action_id,
            "dee_id": manifest.dee_id,
            "model_version": manifest.model_version,
            "model_seed": manifest.model_seed,
            "temperature": manifest.temperature,
            "pre_state_snapshot": manifest.pre_state_snapshot,
            "envelope_data": manifest.envelope_data,
            "expected_result": manifest.expected_result,
            "timestamp": manifest.timestamp.isoformat(),
            "manifest_hash": hashlib.sha256(
                json.dumps(manifest.envelope_data, sort_keys=True).encode()
            ).hexdigest(),
        }
