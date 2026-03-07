"""
TrustKernel State Snapshot & Diff Engine.

Takes minimal relevant state before execution, compares predicted
vs actual post-state, and flags deviations exceeding thresholds.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from trust_kernel.crypto import CryptoProvider
from trust_kernel.models import StateSnapshot, StateDiff, ExecutionEnvelope


class StateEngine:
    """Manages state snapshots and diffs for execution verification.

    Captures pre-execution state, predicts post-state, and after
    execution compares actual results against predictions.
    """

    def __init__(
        self,
        crypto: Optional[CryptoProvider] = None,
        deviation_threshold: float = 0.05,
    ):
        self._crypto = crypto or CryptoProvider()
        self._deviation_threshold = deviation_threshold
        self._snapshots: dict[str, StateSnapshot] = {}

    def capture_pre_state(
        self,
        envelope: ExecutionEnvelope,
        state_data: dict[str, Any],
    ) -> StateSnapshot:
        """Capture a snapshot of relevant state before execution."""
        snapshot = StateSnapshot(
            action_id=envelope.action_id,
            agent_id=envelope.agent_id,
            entries=state_data,
        )
        snapshot.compute_hash()
        self._snapshots[envelope.action_id] = snapshot
        return snapshot

    def capture_post_state(
        self,
        action_id: str,
        agent_id: str,
        state_data: dict[str, Any],
    ) -> StateSnapshot:
        """Capture a snapshot of state after execution."""
        snapshot = StateSnapshot(
            action_id=action_id,
            agent_id=agent_id,
            entries=state_data,
        )
        snapshot.compute_hash()
        return snapshot

    def predict_post_state(
        self,
        pre_state: StateSnapshot,
        expected_changes: list[str],
    ) -> str:
        """Generate a predicted post-state hash based on declared changes."""
        predicted = dict(pre_state.entries)
        for change in expected_changes:
            predicted[f"__change__{change}"] = True
        canonical = json.dumps(predicted, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def compute_diff(
        self,
        action_id: str,
        pre_state: StateSnapshot,
        predicted_post_hash: str,
        actual_post_state: StateSnapshot,
    ) -> StateDiff:
        """Compare predicted vs actual post-state and flag deviations."""
        field_diffs: dict[str, dict[str, Any]] = {}

        pre_entries = pre_state.entries
        post_entries = actual_post_state.entries

        all_keys = set(list(pre_entries.keys()) + list(post_entries.keys()))

        changed_count = 0
        for key in all_keys:
            pre_val = pre_entries.get(key)
            post_val = post_entries.get(key)
            if pre_val != post_val:
                changed_count += 1
                field_diffs[key] = {
                    "before": pre_val,
                    "after": post_val,
                    "type": "modified" if key in pre_entries and key in post_entries
                           else "added" if key not in pre_entries
                           else "removed",
                }

        total_fields = max(len(all_keys), 1)
        deviation_pct = changed_count / total_fields

        hashes_match = predicted_post_hash == actual_post_state.state_hash
        fidelity = 1.0 if hashes_match else max(0.0, 1.0 - deviation_pct)

        diff = StateDiff(
            action_id=action_id,
            pre_state_hash=pre_state.state_hash,
            predicted_post_hash=predicted_post_hash,
            actual_post_hash=actual_post_state.state_hash,
            field_diffs=field_diffs,
            deviation_pct=round(deviation_pct, 4),
            fidelity_score=round(fidelity, 4),
            exceeds_threshold=deviation_pct > self._deviation_threshold,
        )

        return diff

    def get_snapshot(self, action_id: str) -> Optional[StateSnapshot]:
        """Retrieve a stored pre-state snapshot."""
        return self._snapshots.get(action_id)

    def clear_snapshots(self) -> None:
        """Clear all stored snapshots."""
        self._snapshots.clear()
