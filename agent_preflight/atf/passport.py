"""
Action Passport System — HMAC-signed audit artifacts.

Every approved action gets a tamper-proof passport that serves as
the universal audit record. Passports can be verified independently,
stored locally, or forwarded to enterprise control planes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from agent_preflight.atf.models import (
    ActionEnvelope,
    ActionPassport,
    DriftInsight,
    MirrorResult,
    PolicyDecision,
    RiskAssessment,
    SimulationResult,
    Verdict,
)


class PassportAuthority:
    """Issues and verifies Action Passports.

    The authority holds the signing key and acts as the single
    source of truth for passport issuance.
    """

    def __init__(self, secret_key: str):
        self._secret_key = secret_key

    def issue(
        self,
        envelope: ActionEnvelope,
        intent_hash: str,
        risk: RiskAssessment,
        policy: PolicyDecision,
        verdict: Verdict,
        simulation: Optional[SimulationResult] = None,
        drift: Optional[DriftInsight] = None,
        mirror: Optional[MirrorResult] = None,
        human_summary: str = "",
    ) -> ActionPassport:
        """Issue a signed passport for an approved action."""
        passport = ActionPassport(
            action_id=envelope.action_id,
            agent_id=envelope.agent_id,
            intent_hash=intent_hash,
            tool_name=envelope.tool_name,
            risk_score=risk.score,
            simulation_risk=simulation.failure_probability if simulation else None,
            drift_score=drift.anomaly_score if drift else None,
            policy_status="approved" if policy.allow else "denied",
            mirror_executed=mirror is not None,
            mirror_matched=mirror.matches_intent if mirror else None,
            verdict=verdict,
            human_summary=human_summary,
        )
        passport.sign(self._secret_key)
        return passport

    def verify(self, passport: ActionPassport) -> bool:
        """Verify a passport's signature is valid."""
        return passport.verify(self._secret_key)

    def passport_to_db_record(self, passport: ActionPassport) -> dict[str, Any]:
        """Convert passport to a flat dict for database storage."""
        return {
            "passport_id": passport.passport_id,
            "action_id": passport.action_id,
            "agent_id": passport.agent_id,
            "tool_name": passport.tool_name,
            "intent_hash": passport.intent_hash,
            "risk_score": passport.risk_score,
            "simulation_risk": passport.simulation_risk,
            "drift_score": passport.drift_score,
            "policy_status": passport.policy_status,
            "mirror_executed": passport.mirror_executed,
            "mirror_matched": passport.mirror_matched,
            "verdict": passport.verdict.value,
            "human_summary": passport.human_summary,
            "signature": passport.signature,
            "timestamp": passport.timestamp.isoformat(),
        }
