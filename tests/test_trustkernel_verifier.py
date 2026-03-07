"""Tests for TrustKernel execution verifier."""

import pytest
from trust_kernel.verifier import ExecutionVerifier, VerificationResult
from trust_kernel.models import (
    DeterministicExecutionEnvelope,
    ExecutionEnvelope,
    StateDiff,
    StructuredIntent,
    Verdict,
)


def _make_envelope(reversible=True):
    return ExecutionEnvelope(
        agent_id="test-agent",
        tool_name="test_tool",
        intent=StructuredIntent(
            goal="Test",
            reasoning_summary="Testing",
            reversible=reversible,
        ),
    )


def _make_dee(risk_score=0.1):
    return DeterministicExecutionEnvelope(
        action_id="act-1",
        agent_id="test-agent",
        tool_name="test_tool",
        risk_score=risk_score,
    )


class TestExecutionVerifier:
    def setup_method(self):
        self.verifier = ExecutionVerifier(risk_threshold=0.8)

    def test_low_risk_passes(self):
        env = _make_envelope()
        dee = _make_dee(risk_score=0.1)
        result = self.verifier.verify(env, dee)
        assert result.passed
        assert result.verdict == Verdict.ALLOW

    def test_high_risk_blocks(self):
        env = _make_envelope()
        dee = _make_dee(risk_score=0.9)
        result = self.verifier.verify(env, dee)
        assert not result.passed
        assert result.verdict == Verdict.BLOCK
        assert "risk_bound" in result.checks_failed

    def test_irreversible_requires_consent(self):
        env = _make_envelope(reversible=False)
        dee = _make_dee(risk_score=0.1)
        result = self.verifier.verify(env, dee, operator_consent=False)
        assert not result.passed
        assert result.verdict == Verdict.REQUIRE_APPROVAL

    def test_irreversible_with_consent_passes(self):
        env = _make_envelope(reversible=False)
        dee = _make_dee(risk_score=0.1)
        result = self.verifier.verify(env, dee, operator_consent=True)
        assert result.passed
        assert result.verdict == Verdict.ALLOW

    def test_policy_violation_blocks(self):
        env = _make_envelope()
        dee = _make_dee(risk_score=0.1)
        result = self.verifier.verify(env, dee, policy_approved=False)
        assert not result.passed
        assert "policy_compliance" in result.checks_failed

    def test_budget_exceeded_blocks(self):
        env = _make_envelope()
        dee = _make_dee(risk_score=0.1)
        result = self.verifier.verify(env, dee, budget_ok=False)
        assert not result.passed
        assert "budget" in result.checks_failed

    def test_state_fidelity_check(self):
        env = _make_envelope()
        dee = _make_dee(risk_score=0.1)
        diff = StateDiff(
            action_id="act-1",
            pre_state_hash="a",
            predicted_post_hash="b",
            actual_post_hash="c",
            fidelity_score=0.5,
            exceeds_threshold=True,
        )
        result = self.verifier.verify(env, dee, state_diff=diff)
        assert not result.passed
        assert "state_fidelity" in result.checks_failed

    def test_to_dict(self):
        env = _make_envelope()
        dee = _make_dee()
        result = self.verifier.verify(env, dee)
        d = result.to_dict()
        assert "passed" in d
        assert "verdict" in d
        assert "checks_performed" in d
