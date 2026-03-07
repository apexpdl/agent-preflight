"""
TrustKernel Execution Verifier.

Before applying an action, verifies:
1. Predicted vs actual state in sandbox
2. Risk bound check (< threshold)
3. Consent signatures from operator & policy engine
Only allows execution if all checks pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from trust_kernel.models import (
    DeterministicExecutionEnvelope,
    ExecutionEnvelope,
    StateDiff,
    Verdict,
)


@dataclass
class VerificationResult:
    """Result of pre-execution verification."""
    passed: bool
    verdict: Verdict
    checks_performed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    fidelity_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verdict": self.verdict.value,
            "checks_performed": self.checks_performed,
            "checks_failed": self.checks_failed,
            "reasons": self.reasons,
            "risk_score": self.risk_score,
            "fidelity_score": self.fidelity_score,
        }


class ExecutionVerifier:
    """Verifies all preconditions before allowing execution.

    Checks:
    - State fidelity (predicted matches sandbox)
    - Risk bound (below threshold)
    - Operator consent (for irreversible actions)
    - Policy compliance
    - Cost budget
    """

    def __init__(
        self,
        risk_threshold: float = 0.8,
        fidelity_threshold: float = 0.9,
        require_consent_for_irreversible: bool = True,
    ):
        self._risk_threshold = risk_threshold
        self._fidelity_threshold = fidelity_threshold
        self._require_consent = require_consent_for_irreversible

    def verify(
        self,
        envelope: ExecutionEnvelope,
        dee: DeterministicExecutionEnvelope,
        state_diff: Optional[StateDiff] = None,
        operator_consent: bool = False,
        policy_approved: bool = True,
        budget_ok: bool = True,
    ) -> VerificationResult:
        """Run all verification checks."""
        checks_performed: list[str] = []
        checks_failed: list[str] = []
        reasons: list[str] = []

        # 1. Risk bound check
        checks_performed.append("risk_bound")
        if dee.risk_score > self._risk_threshold:
            checks_failed.append("risk_bound")
            reasons.append(
                f"Risk score {dee.risk_score:.4f} exceeds threshold {self._risk_threshold}"
            )

        # 2. State fidelity check
        if state_diff is not None:
            checks_performed.append("state_fidelity")
            if state_diff.fidelity_score < self._fidelity_threshold:
                checks_failed.append("state_fidelity")
                reasons.append(
                    f"Fidelity {state_diff.fidelity_score:.4f} below "
                    f"threshold {self._fidelity_threshold}"
                )

            checks_performed.append("state_deviation")
            if state_diff.exceeds_threshold:
                checks_failed.append("state_deviation")
                reasons.append(
                    f"State deviation {state_diff.deviation_pct:.2%} "
                    f"exceeds allowed threshold"
                )

        # 3. Operator consent for irreversible actions
        if self._require_consent and not envelope.intent.reversible:
            checks_performed.append("operator_consent")
            if not operator_consent:
                checks_failed.append("operator_consent")
                reasons.append(
                    "Irreversible action requires operator consent"
                )

        # 4. Policy compliance
        checks_performed.append("policy_compliance")
        if not policy_approved:
            checks_failed.append("policy_compliance")
            reasons.append("Action violates active policy rules")

        # 5. Budget check
        checks_performed.append("budget")
        if not budget_ok:
            checks_failed.append("budget")
            reasons.append("Action exceeds cost budget")

        # Determine verdict
        passed = len(checks_failed) == 0
        if passed:
            verdict = Verdict.ALLOW
        elif "operator_consent" in checks_failed and len(checks_failed) == 1:
            verdict = Verdict.REQUIRE_APPROVAL
        else:
            verdict = Verdict.BLOCK

        return VerificationResult(
            passed=passed,
            verdict=verdict,
            checks_performed=checks_performed,
            checks_failed=checks_failed,
            reasons=reasons,
            risk_score=dee.risk_score,
            fidelity_score=state_diff.fidelity_score if state_diff else 1.0,
        )
