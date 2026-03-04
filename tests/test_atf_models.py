"""Tests for ATF Pydantic models."""

import pytest
from agent_preflight.atf.models import (
    ActionEnvelope,
    ActionPassport,
    ActionType,
    CorrectionFeedback,
    DriftInsight,
    ExecutionMode,
    FileDelta,
    MirrorResult,
    PipelineResult,
    PolicyDecision,
    PolicyViolation,
    RiskAssessment,
    SimulationResult,
    StructuredIntent,
    Verdict,
)


def _make_envelope(**overrides):
    defaults = {
        "agent_id": "test-agent",
        "tool_name": "test_tool",
        "arguments": {"key": "value"},
        "intent": StructuredIntent(
            goal="Test goal",
            reasoning_summary="Test reasoning",
        ),
    }
    defaults.update(overrides)
    return ActionEnvelope(**defaults)


class TestStructuredIntent:
    def test_minimal(self):
        intent = StructuredIntent(goal="Do X", reasoning_summary="Because Y")
        assert intent.goal == "Do X"
        assert intent.confidence == 0.5
        assert intent.irreversible is False

    def test_full(self):
        intent = StructuredIntent(
            goal="Delete records",
            reasoning_summary="Cleanup old data",
            expected_state_changes=["row count decreases"],
            external_calls=["api.example.com"],
            irreversible=True,
            estimated_cost=99.99,
            confidence=0.9,
        )
        assert intent.irreversible is True
        assert intent.estimated_cost == 99.99

    def test_validation(self):
        with pytest.raises(Exception):
            StructuredIntent(goal="", reasoning_summary="x")  # empty goal


class TestActionEnvelope:
    def test_creation(self):
        e = _make_envelope()
        assert e.agent_id == "test-agent"
        assert e.tool_name == "test_tool"
        assert e.action_id  # auto-generated

    def test_fingerprint_deterministic(self):
        e = _make_envelope()
        assert e.fingerprint() == e.fingerprint()

    def test_fingerprint_differs(self):
        e1 = _make_envelope(tool_name="a")
        e2 = _make_envelope(tool_name="b")
        assert e1.fingerprint() != e2.fingerprint()


class TestActionPassport:
    def test_sign_and_verify(self):
        passport = ActionPassport(
            action_id="a1",
            agent_id="agent1",
            intent_hash="hash123",
            tool_name="tool1",
            risk_score=0.5,
            policy_status="approved",
        )
        passport.sign("my-secret")
        assert passport.signature != ""
        assert passport.verify("my-secret")

    def test_verify_fails_wrong_key(self):
        passport = ActionPassport(
            action_id="a1",
            agent_id="agent1",
            intent_hash="hash123",
            tool_name="tool1",
            risk_score=0.5,
            policy_status="approved",
        )
        passport.sign("correct-key")
        assert not passport.verify("wrong-key")


class TestPipelineResult:
    def test_to_agent_response(self):
        result = PipelineResult(
            action_id="a1",
            verdict=Verdict.ALLOW,
            risk_assessment=RiskAssessment(score=0.3, flags=["test"]),
            policy_decision=PolicyDecision(allow=True),
            human_summary="Low risk action",
        )
        resp = result.to_agent_response()
        assert resp["verdict"] == "allow"
        assert resp["risk_score"] == 0.3
        assert "test" in resp["flags"]

    def test_with_simulation(self):
        result = PipelineResult(
            action_id="a1",
            verdict=Verdict.WARN,
            risk_assessment=RiskAssessment(score=0.6),
            simulation_result=SimulationResult(
                failure_probability=0.35,
                volatility_score=0.5,
                cascade_probability=0.2,
                confidence_interval=(0.2, 0.5),
                rollout_count=50,
            ),
            policy_decision=PolicyDecision(allow=True),
        )
        resp = result.to_agent_response()
        assert resp["failure_probability"] == 0.35
        assert resp["volatility_index"] == 0.5
