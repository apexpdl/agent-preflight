"""
TrustKernel Operator Consensus Layer.

Configurable M-of-N approval for irreversible actions. Supports
human operators, automated policies, and hardware key signatures.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from trust_kernel.crypto import CryptoProvider
from trust_kernel.models import (
    ConsensusRequest,
    ConsensusVote,
    ConsentStatus,
    ExecutionEnvelope,
)


class OperatorConsensus:
    """M-of-N operator consensus for high-risk actions.

    When an irreversible action requires human approval, this module
    creates a consensus request and collects votes until the required
    threshold is met or the request expires.
    """

    def __init__(
        self,
        required_approvals: int = 1,
        expiry_minutes: int = 30,
        crypto: Optional[CryptoProvider] = None,
    ):
        self._required = required_approvals
        self._expiry_minutes = expiry_minutes
        self._crypto = crypto or CryptoProvider()
        self._requests: dict[str, ConsensusRequest] = {}
        self._votes: dict[str, list[ConsensusVote]] = {}

    def create_request(
        self,
        envelope: ExecutionEnvelope,
        dee_id: str = "",
        risk_score: float = 0.0,
        summary: str = "",
    ) -> ConsensusRequest:
        """Create a new consensus request for an action."""
        request = ConsensusRequest(
            action_id=envelope.action_id,
            dee_id=dee_id,
            agent_id=envelope.agent_id,
            tool_name=envelope.tool_name,
            risk_score=risk_score,
            required_approvals=self._required,
            summary=summary or f"Approval needed: {envelope.tool_name} (risk: {risk_score:.2f})",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=self._expiry_minutes),
        )
        self._requests[request.request_id] = request
        self._votes[request.request_id] = []
        return request

    def cast_vote(
        self,
        request_id: str,
        operator_id: str,
        approved: bool,
        reason: str = "",
    ) -> Optional[ConsensusVote]:
        """Cast an approval or rejection vote."""
        request = self._requests.get(request_id)
        if not request or request.status != ConsentStatus.PENDING:
            return None

        # Check if expired
        if request.expires_at and datetime.now(timezone.utc) > request.expires_at:
            request.status = ConsentStatus.EXPIRED
            return None

        # Check if operator already voted
        existing_votes = self._votes.get(request_id, [])
        if any(v.operator_id == operator_id for v in existing_votes):
            return None  # Already voted

        # Create signed vote
        vote_data = f"{request_id}:{operator_id}:{approved}:{reason}"
        signature = self._crypto.sign(vote_data.encode(), f"operator:{operator_id}")

        vote = ConsensusVote(
            request_id=request_id,
            operator_id=operator_id,
            approved=approved,
            signature=signature,
            reason=reason,
        )
        existing_votes.append(vote)
        self._votes[request_id] = existing_votes

        # Update request status
        approvals = sum(1 for v in existing_votes if v.approved)
        rejections = sum(1 for v in existing_votes if not v.approved)
        request.collected_approvals = approvals

        if approvals >= request.required_approvals:
            request.status = ConsentStatus.APPROVED
        elif rejections > 0:
            # Any rejection blocks
            request.status = ConsentStatus.REJECTED

        return vote

    def is_approved(self, request_id: str) -> bool:
        """Check if a consensus request has been approved."""
        request = self._requests.get(request_id)
        if not request:
            return False
        return request.status == ConsentStatus.APPROVED

    def is_pending(self, request_id: str) -> bool:
        """Check if a consensus request is still pending."""
        request = self._requests.get(request_id)
        if not request:
            return False
        if request.expires_at and datetime.now(timezone.utc) > request.expires_at:
            request.status = ConsentStatus.EXPIRED
            return False
        return request.status == ConsentStatus.PENDING

    def get_request(self, request_id: str) -> Optional[ConsensusRequest]:
        """Get a consensus request by ID."""
        return self._requests.get(request_id)

    def get_votes(self, request_id: str) -> list[ConsensusVote]:
        """Get all votes for a request."""
        return self._votes.get(request_id, [])

    def get_pending_requests(self) -> list[ConsensusRequest]:
        """Get all pending consensus requests."""
        now = datetime.now(timezone.utc)
        pending = []
        for req in self._requests.values():
            if req.status == ConsentStatus.PENDING:
                if req.expires_at and now > req.expires_at:
                    req.status = ConsentStatus.EXPIRED
                else:
                    pending.append(req)
        return pending

    def get_request_summary(self, request_id: str) -> dict[str, Any]:
        """Get a summary of a consensus request and its votes."""
        request = self._requests.get(request_id)
        if not request:
            return {}
        votes = self._votes.get(request_id, [])
        return {
            "request_id": request.request_id,
            "action_id": request.action_id,
            "tool_name": request.tool_name,
            "risk_score": request.risk_score,
            "status": request.status.value,
            "required": request.required_approvals,
            "collected": request.collected_approvals,
            "votes": [
                {
                    "operator_id": v.operator_id,
                    "approved": v.approved,
                    "reason": v.reason,
                }
                for v in votes
            ],
            "summary": request.summary,
        }
