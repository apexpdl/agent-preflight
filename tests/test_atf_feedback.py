"""Tests for ATF Self-Correcting Feedback Loop."""

import pytest
from agent_preflight.atf.feedback import FeedbackGenerator
from agent_preflight.atf.models import (
    ActionEnvelope,
    MirrorResult,
    PolicyDecision,
    PolicyViolation,
    RiskAssessment,
    SimulationResult,
    StructuredIntent,
)


def _make_envelope(goal="Test goal"):
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name="delete_records",
        arguments={"table": "users"},
        intent=StructuredIntent(
            goal=goal,
            reasoning_summary="Cleanup",
            irreversible=True,
            estimated_cost=50,
        ),
    )


class TestFeedbackGenerator:
    def test_generates_correction(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(
            score=0.9,
            flags=["irreversible", "destructive_tool"],
        )
        feedback = gen.generate(_make_envelope(), risk)
        assert feedback.blocked
        assert len(feedback.violations) > 0
        assert len(feedback.suggestions) > 0

    def test_policy_feedback(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(score=0.5)
        policy = PolicyDecision(
            allow=False,
            violations=[PolicyViolation(
                rule_name="no_delete",
                description="Deletion not allowed",
            )],
        )
        feedback = gen.generate(_make_envelope(), risk, policy=policy)
        assert any("no_delete" in v for v in feedback.violations)

    def test_mirror_feedback(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(score=0.5)
        mirror = MirrorResult(
            matches_intent=False,
            mismatch_details=["Unexpected file deletion"],
            external_attempts=["POST https://api.example.com"],
        )
        feedback = gen.generate(_make_envelope(), risk, mirror=mirror)
        assert any("mismatch" in v.lower() for v in feedback.violations)

    def test_human_summary_low_risk(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(score=0.1)
        summary = gen.generate_human_summary(
            ActionEnvelope(
                agent_id="my-agent",
                tool_name="read_file",
                arguments={},
                intent=StructuredIntent(goal="Read config", reasoning_summary="Check settings"),
            ),
            risk,
        )
        assert "my-agent" in summary
        assert "low-risk" in summary.lower()

    def test_human_summary_critical(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(
            score=0.95,
            flags=["irreversible", "destructive_tool", "sensitive_path"],
        )
        summary = gen.generate_human_summary(_make_envelope(), risk)
        assert "CRITICAL" in summary
        assert "irreversible" in summary.lower()

    def test_human_summary_with_simulation(self):
        gen = FeedbackGenerator()
        risk = RiskAssessment(score=0.6, flags=["test"])
        sim = SimulationResult(
            failure_probability=0.45,
            cascade_probability=0.3,
            rollout_count=100,
        )
        summary = gen.generate_human_summary(_make_envelope(), risk, sim)
        assert "45%" in summary
        assert "100" in summary
