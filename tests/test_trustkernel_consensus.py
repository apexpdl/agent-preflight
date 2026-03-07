"""Tests for TrustKernel operator consensus."""

import pytest
from trust_kernel.consensus import OperatorConsensus
from trust_kernel.models import (
    ConsentStatus,
    ExecutionEnvelope,
    StructuredIntent,
)


def _make_envelope():
    return ExecutionEnvelope(
        agent_id="test-agent",
        tool_name="delete_production_db",
        intent=StructuredIntent(
            goal="Clean up old records",
            reasoning_summary="Remove stale data",
            reversible=False,
        ),
    )


class TestOperatorConsensus:
    def setup_method(self):
        self.consensus = OperatorConsensus(required_approvals=2)

    def test_create_request(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        assert req.status == ConsentStatus.PENDING
        assert req.required_approvals == 2

    def test_single_approval_not_enough(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        self.consensus.cast_vote(req.request_id, "operator-1", True)
        assert not self.consensus.is_approved(req.request_id)
        assert self.consensus.is_pending(req.request_id)

    def test_two_approvals_sufficient(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        self.consensus.cast_vote(req.request_id, "operator-1", True)
        self.consensus.cast_vote(req.request_id, "operator-2", True)
        assert self.consensus.is_approved(req.request_id)

    def test_rejection_blocks(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        self.consensus.cast_vote(req.request_id, "operator-1", False, "Too risky")
        assert not self.consensus.is_approved(req.request_id)
        assert req.status == ConsentStatus.REJECTED

    def test_duplicate_vote_ignored(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        v1 = self.consensus.cast_vote(req.request_id, "operator-1", True)
        v2 = self.consensus.cast_vote(req.request_id, "operator-1", True)
        assert v1 is not None
        assert v2 is None

    def test_get_pending_requests(self):
        env = _make_envelope()
        self.consensus.create_request(env, risk_score=0.85)
        pending = self.consensus.get_pending_requests()
        assert len(pending) == 1

    def test_get_request_summary(self):
        env = _make_envelope()
        req = self.consensus.create_request(env, risk_score=0.85)
        self.consensus.cast_vote(req.request_id, "op-1", True, "Looks good")
        summary = self.consensus.get_request_summary(req.request_id)
        assert summary["required"] == 2
        assert summary["collected"] == 1
        assert len(summary["votes"]) == 1

    def test_vote_on_nonexistent_request(self):
        vote = self.consensus.cast_vote("nonexistent", "op-1", True)
        assert vote is None
