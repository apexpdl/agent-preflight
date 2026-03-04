"""
Risk Engine v2 — Fast deterministic risk scoring (<20ms target).

No LLM calls. Pure computation using weighted scoring with
logistic-regression-style feature weighting.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Optional

from agent_preflight.atf.models import ActionEnvelope, RiskAssessment

# ---------------------------------------------------------------------------
# Sensitive path patterns
# ---------------------------------------------------------------------------

_SENSITIVE_PATHS = [
    re.compile(r"(/etc/|\\etc\\)", re.IGNORECASE),
    re.compile(r"\.env", re.IGNORECASE),
    re.compile(r"(prod|production)", re.IGNORECASE),
    re.compile(r"(secret|credential|password|token|key)", re.IGNORECASE),
    re.compile(r"(\.ssh|\.gnupg|\.aws)", re.IGNORECASE),
    re.compile(r"(/root/|/home/.*/\.)", re.IGNORECASE),
    re.compile(r"(database|\.db|\.sqlite)", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Dangerous tool patterns
# ---------------------------------------------------------------------------

_DESTRUCTIVE_TOOLS = re.compile(
    r"(delete|drop|truncate|remove|purge|destroy|kill|terminate|format|wipe|rm)",
    re.IGNORECASE,
)
_NETWORK_TOOLS = re.compile(
    r"(send|email|slack|webhook|notify|post|push|publish|broadcast|sms)",
    re.IGNORECASE,
)
_FINANCIAL_TOOLS = re.compile(
    r"(pay|transfer|charge|invoice|refund|purchase|wire|withdraw|debit|credit)",
    re.IGNORECASE,
)
_SHELL_TOOLS = re.compile(
    r"(exec|shell|bash|system|subprocess|eval|run_command|os\.system)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Feature weights (logistic regression style)
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, float] = {
    "irreversible": 3.0,
    "destructive_tool": 2.5,
    "financial_tool": 2.8,
    "shell_tool": 2.2,
    "network_tool": 1.5,
    "sensitive_path": 2.0,
    "high_cost": 1.8,
    "low_confidence": 1.5,
    "wide_scope": 1.2,
    "drift_similarity": 2.0,
    "external_calls": 1.3,
    "multiple_state_changes": 1.0,
}

_BIAS = -2.0  # Base bias — shifts sigmoid so low-risk actions stay low


def _sigmoid(x: float) -> float:
    """Logistic sigmoid function."""
    return 1.0 / (1.0 + math.exp(-x))


class RiskEngine:
    """Fast deterministic risk scoring engine.

    Computes risk as sigmoid(sum(feature_i * weight_i) + bias).
    Runs in <20ms with no external calls.
    """

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        bias: float = _BIAS,
        mirror_threshold: float = 0.5,
    ):
        self._weights = weights or dict(_WEIGHTS)
        self._bias = bias
        self._mirror_threshold = mirror_threshold

    async def assess(
        self,
        envelope: ActionEnvelope,
        drift_similarity: float = 0.0,
    ) -> RiskAssessment:
        """Compute risk score for an action envelope."""
        start = time.perf_counter()

        features: dict[str, float] = {}
        flags: list[str] = []

        # Feature: irreversibility
        if envelope.intent.irreversible:
            features["irreversible"] = 1.0
            flags.append("irreversible")

        # Feature: destructive tool name
        if _DESTRUCTIVE_TOOLS.search(envelope.tool_name):
            features["destructive_tool"] = 1.0
            flags.append("destructive_tool")

        # Feature: financial tool
        if _FINANCIAL_TOOLS.search(envelope.tool_name):
            features["financial_tool"] = 1.0
            flags.append("financial_operation")

        # Feature: shell execution
        if _SHELL_TOOLS.search(envelope.tool_name):
            features["shell_tool"] = 1.0
            flags.append("shell_execution")

        # Feature: network/external communication
        if _NETWORK_TOOLS.search(envelope.tool_name):
            features["network_tool"] = 1.0
            flags.append("external_communication")

        # Feature: sensitive paths in arguments or targets
        all_targets = " ".join(
            envelope.resource_targets
            + [str(v) for v in envelope.arguments.values()]
        )
        for pattern in _SENSITIVE_PATHS:
            if pattern.search(all_targets):
                features["sensitive_path"] = 1.0
                flags.append("sensitive_path")
                break

        # Feature: high estimated cost
        cost = envelope.intent.estimated_cost
        if cost > 100:
            features["high_cost"] = min(cost / 500, 1.0)
            flags.append(f"high_cost_${cost:.2f}")
        elif cost > 10:
            features["high_cost"] = cost / 500
            flags.append(f"moderate_cost_${cost:.2f}")

        # Feature: low confidence
        if envelope.intent.confidence < 0.5:
            features["low_confidence"] = 1.0 - envelope.intent.confidence
            flags.append("low_confidence")

        # Feature: wide scope (many state changes)
        n_changes = len(envelope.intent.expected_state_changes)
        if n_changes > 5:
            features["wide_scope"] = min(n_changes / 20, 1.0)
            flags.append(f"wide_scope_{n_changes}_changes")

        # Feature: multiple state changes
        if n_changes > 2:
            features["multiple_state_changes"] = min(n_changes / 10, 1.0)

        # Feature: external calls declared
        n_external = len(envelope.intent.external_calls)
        if n_external > 0:
            features["external_calls"] = min(n_external / 5, 1.0)
            flags.append(f"external_calls_{n_external}")

        # Feature: drift similarity to known failures
        if drift_similarity > 0.3:
            features["drift_similarity"] = drift_similarity
            flags.append(f"drift_similar_{drift_similarity:.2f}")

        # Compute weighted sum
        weighted_sum = self._bias
        breakdown: dict[str, float] = {}
        for feature_name, feature_value in features.items():
            weight = self._weights.get(feature_name, 1.0)
            contribution = feature_value * weight
            weighted_sum += contribution
            breakdown[feature_name] = round(contribution, 4)

        # Apply sigmoid
        score = _sigmoid(weighted_sum)
        score = round(score, 4)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return RiskAssessment(
            score=score,
            flags=flags,
            requires_mirror=score >= self._mirror_threshold,
            breakdown=breakdown,
            computation_time_ms=round(elapsed_ms, 3),
        )

    def update_weights(self, updates: dict[str, float]) -> None:
        """Hot-update weights without restart."""
        self._weights.update(updates)
