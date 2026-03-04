"""Tests for ATF Action Passport system."""

import pytest
from agent_preflight.atf.models import (
    ActionEnvelope,
    PolicyDecision,
    RiskAssessment,
    StructuredIntent,
    Verdict,
)
from agent_preflight.atf.passport import PassportAuthority


def _make_envelope():
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name="test_tool",
        arguments={},
        intent=StructuredIntent(goal="Test", reasoning_summary="Test"),
    )


class TestPassportAuthority:
    def test_issue_passport(self):
        authority = PassportAuthority("test-secret")
        passport = authority.issue(
            envelope=_make_envelope(),
            intent_hash="abc123",
            risk=RiskAssessment(score=0.3),
            policy=PolicyDecision(allow=True),
            verdict=Verdict.ALLOW,
        )
        assert passport.passport_id
        assert passport.signature
        assert passport.risk_score == 0.3
        assert passport.verdict == Verdict.ALLOW

    def test_verify_valid(self):
        authority = PassportAuthority("test-secret")
        passport = authority.issue(
            envelope=_make_envelope(),
            intent_hash="abc123",
            risk=RiskAssessment(score=0.5),
            policy=PolicyDecision(allow=True),
            verdict=Verdict.WARN,
        )
        assert authority.verify(passport)

    def test_verify_tampered(self):
        authority = PassportAuthority("test-secret")
        passport = authority.issue(
            envelope=_make_envelope(),
            intent_hash="abc123",
            risk=RiskAssessment(score=0.5),
            policy=PolicyDecision(allow=True),
            verdict=Verdict.ALLOW,
        )
        passport.risk_score = 0.1  # Tamper!
        passport.sign("wrong-key")
        assert not authority.verify(passport)

    def test_to_db_record(self):
        authority = PassportAuthority("secret")
        passport = authority.issue(
            envelope=_make_envelope(),
            intent_hash="hash1",
            risk=RiskAssessment(score=0.2),
            policy=PolicyDecision(allow=True),
            verdict=Verdict.ALLOW,
            human_summary="Low risk action",
        )
        record = authority.passport_to_db_record(passport)
        assert record["passport_id"] == passport.passport_id
        assert record["human_summary"] == "Low risk action"
        assert record["signature"]
