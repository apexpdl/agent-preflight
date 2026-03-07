"""
TrustKernel — The central execution orchestrator.

Ties together all modules: intent compilation, deterministic planning,
state management, risk assessment, simulation, verification, consensus,
rollback, audit logging, and reproducibility.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from trust_kernel.consensus import OperatorConsensus
from trust_kernel.cost_governor import CostGovernor
from trust_kernel.crypto import CryptoProvider
from trust_kernel.ledger import LiabilityLedger
from trust_kernel.models import (
    CostBudget,
    DeterministicExecutionEnvelope,
    ExecutionEnvelope,
    StateSnapshot,
    Verdict,
)
from trust_kernel.planner import DeterministicPlanner, ExecutionDAG
from trust_kernel.reproducibility import ReproducibilityEngine
from trust_kernel.rollback import RollbackController
from trust_kernel.state_engine import StateEngine
from trust_kernel.verifier import ExecutionVerifier, VerificationResult


class TrustKernelConfig:
    """Configuration for TrustKernel."""

    def __init__(
        self,
        db_path: str = ":memory:",
        signing_key: Optional[str] = None,
        hmac_key: Optional[str] = None,
        risk_threshold: float = 0.8,
        fidelity_threshold: float = 0.9,
        require_consent_for_irreversible: bool = True,
        required_approvals: int = 1,
        consensus_expiry_minutes: int = 30,
        budget: Optional[CostBudget] = None,
        model_version: str = "",
    ):
        self.db_path = db_path
        self.signing_key = signing_key
        self.hmac_key = hmac_key
        self.risk_threshold = risk_threshold
        self.fidelity_threshold = fidelity_threshold
        self.require_consent_for_irreversible = require_consent_for_irreversible
        self.required_approvals = required_approvals
        self.consensus_expiry_minutes = consensus_expiry_minutes
        self.budget = budget
        self.model_version = model_version


class TrustKernelResult:
    """Complete result from the TrustKernel pipeline."""

    def __init__(
        self,
        action_id: str,
        verdict: Verdict,
        dee: DeterministicExecutionEnvelope,
        verification: VerificationResult,
        dag: Optional[ExecutionDAG] = None,
        consensus_request_id: Optional[str] = None,
        pipeline_time_ms: float = 0.0,
        cost_alerts: Optional[list] = None,
    ):
        self.action_id = action_id
        self.verdict = verdict
        self.dee = dee
        self.verification = verification
        self.dag = dag
        self.consensus_request_id = consensus_request_id
        self.pipeline_time_ms = pipeline_time_ms
        self.cost_alerts = cost_alerts or []

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action_id": self.action_id,
            "verdict": self.verdict.value,
            "risk_score": self.dee.risk_score,
            "fidelity_score": self.dee.fidelity_score,
            "rollback_coverage": self.dee.rollback_coverage,
            "pipeline_time_ms": self.pipeline_time_ms,
            "signatures": {
                "agent": self.dee.agent_signature[:16] + "..." if self.dee.agent_signature else "",
                "operator": self.dee.operator_signature[:16] + "..." if self.dee.operator_signature else "",
                "policy": self.dee.policy_signature[:16] + "..." if self.dee.policy_signature else "",
            },
            "verification": self.verification.to_dict(),
        }
        if self.dag:
            result["dag"] = self.dag.to_dict()
        if self.consensus_request_id:
            result["consensus_request_id"] = self.consensus_request_id
        if self.cost_alerts:
            result["cost_alerts"] = [
                {"type": a.alert_type, "metric": a.metric, "message": a.message}
                for a in self.cost_alerts
            ]
        return result


class TrustKernel:
    """The central TrustKernel execution orchestrator.

    Pipeline:
    1. Parse & validate intent
    2. Plan execution (DAG)
    3. Capture pre-state
    4. Compute risk score
    5. Check cost budget
    6. Build DEE (Deterministic Execution Envelope)
    7. Sign with cryptographic keys
    8. Verify all preconditions
    9. Request consensus (if irreversible)
    10. Execute (or block)
    11. Capture post-state & compute diff
    12. Record in liability ledger
    13. Create replay manifest

    Usage:
        kernel = TrustKernel()
        await kernel.initialize()
        result = await kernel.execute(envelope)
    """

    def __init__(self, config: Optional[TrustKernelConfig] = None):
        self._config = config or TrustKernelConfig()
        self._crypto = CryptoProvider(
            signing_key=self._config.signing_key,
            hmac_key=self._config.hmac_key,
        )
        self._planner = DeterministicPlanner()
        self._state_engine = StateEngine(crypto=self._crypto)
        self._verifier = ExecutionVerifier(
            risk_threshold=self._config.risk_threshold,
            fidelity_threshold=self._config.fidelity_threshold,
            require_consent_for_irreversible=self._config.require_consent_for_irreversible,
        )
        self._rollback = RollbackController()
        self._ledger = LiabilityLedger(
            db_path=self._config.db_path,
            crypto=self._crypto,
        )
        self._consensus = OperatorConsensus(
            required_approvals=self._config.required_approvals,
            expiry_minutes=self._config.consensus_expiry_minutes,
            crypto=self._crypto,
        )
        self._cost_governor = CostGovernor(
            budget=self._config.budget,
        )
        self._reproducibility = ReproducibilityEngine()
        self._tool_registry: dict[str, Callable] = {}
        self._initialized = False

    @property
    def ledger(self) -> LiabilityLedger:
        return self._ledger

    @property
    def consensus(self) -> OperatorConsensus:
        return self._consensus

    @property
    def cost_governor(self) -> CostGovernor:
        return self._cost_governor

    @property
    def crypto(self) -> CryptoProvider:
        return self._crypto

    @property
    def rollback(self) -> RollbackController:
        return self._rollback

    @property
    def reproducibility(self) -> ReproducibilityEngine:
        return self._reproducibility

    async def initialize(self) -> None:
        """Initialize database and all subsystems."""
        await self._ledger.initialize()
        self._initialized = True

    def register_tool(self, name: str, fn: Callable) -> None:
        """Register a tool function for execution."""
        self._tool_registry[name] = fn

    async def execute(
        self,
        envelope: ExecutionEnvelope,
        pre_state: Optional[dict[str, Any]] = None,
        risk_score: Optional[float] = None,
        operator_consent: bool = False,
        tool_fn: Optional[Callable] = None,
    ) -> TrustKernelResult:
        """Run the full TrustKernel pipeline for an action."""
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        # 1. Plan execution
        dag = self._planner.plan_single(envelope)

        # 2. Capture pre-state
        state_data = pre_state or {"__empty__": True}
        pre_snapshot = self._state_engine.capture_pre_state(envelope, state_data)

        # 3. Compute risk (use provided or estimate from intent)
        computed_risk = risk_score if risk_score is not None else self._estimate_risk(envelope)

        # 4. Check cost budget
        budget_ok, cost_alerts = self._cost_governor.can_execute(envelope)

        # 5. Build DEE
        intent_digest = envelope.fingerprint()
        predicted_post_hash = self._state_engine.predict_post_state(
            pre_snapshot, envelope.intent.expected_state_changes
        )

        dee = DeterministicExecutionEnvelope(
            action_id=envelope.action_id,
            agent_id=envelope.agent_id,
            tool_name=envelope.tool_name,
            intent_digest=intent_digest,
            pre_state_hash=pre_snapshot.state_hash,
            predicted_post_hash=predicted_post_hash,
            risk_score=computed_risk,
            verdict=Verdict.ALLOW,  # Provisional
        )

        # 6. Sign with cryptographic keys
        dee.agent_signature = self._crypto.sign(dee.canonical_bytes(), "agent")
        dee.policy_signature = self._crypto.sign(dee.canonical_bytes(), "policy")

        # 7. Compute rollback coverage
        self._rollback.create_plan(envelope.action_id)
        dee.rollback_coverage = 1.0 if envelope.intent.reversible else 0.0

        # 8. Verify all preconditions
        verification = self._verifier.verify(
            envelope=envelope,
            dee=dee,
            operator_consent=operator_consent,
            policy_approved=True,
            budget_ok=budget_ok,
        )
        dee.verdict = verification.verdict

        # 9. Handle consensus for irreversible actions
        consensus_request_id = None
        if verification.verdict == Verdict.REQUIRE_APPROVAL:
            request = self._consensus.create_request(
                envelope=envelope,
                dee_id=dee.dee_id,
                risk_score=computed_risk,
            )
            consensus_request_id = request.request_id

        # 10. Charge budget if executing
        if verification.passed:
            self._cost_governor.charge(envelope)

        # 11. Record in liability ledger
        await self._ledger.append_from_dee(dee)

        # 12. Create replay manifest
        self._reproducibility.create_manifest(
            envelope=envelope,
            pre_state=pre_snapshot,
            model_version=self._config.model_version,
            dee_id=dee.dee_id,
        )

        elapsed = (time.perf_counter() - start) * 1000

        return TrustKernelResult(
            action_id=envelope.action_id,
            verdict=dee.verdict,
            dee=dee,
            verification=verification,
            dag=dag,
            consensus_request_id=consensus_request_id,
            pipeline_time_ms=round(elapsed, 3),
            cost_alerts=cost_alerts,
        )

    def _estimate_risk(self, envelope: ExecutionEnvelope) -> float:
        """Quick risk estimation from intent metadata."""
        risk = 0.1  # Base

        if not envelope.intent.reversible:
            risk += 0.3
        if envelope.intent.estimated_cost > 100:
            risk += 0.2
        if envelope.intent.confidence < 0.5:
            risk += 0.15
        if envelope.intent.mutability_class.value == "destructive":
            risk += 0.25
        if envelope.intent.external_dependency_count > 2:
            risk += 0.1

        return min(risk, 1.0)

    async def approve_consensus(
        self, request_id: str, operator_id: str, reason: str = ""
    ) -> bool:
        """Approve a pending consensus request."""
        vote = self._consensus.cast_vote(request_id, operator_id, True, reason)
        if vote:
            await self._ledger.store_consensus_vote({
                "vote_id": vote.vote_id,
                "request_id": vote.request_id,
                "operator_id": vote.operator_id,
                "approved": vote.approved,
                "signature": vote.signature,
                "reason": vote.reason,
                "timestamp": vote.timestamp.isoformat(),
            })
        return self._consensus.is_approved(request_id)

    async def reject_consensus(
        self, request_id: str, operator_id: str, reason: str = ""
    ) -> None:
        """Reject a pending consensus request."""
        vote = self._consensus.cast_vote(request_id, operator_id, False, reason)
        if vote:
            await self._ledger.store_consensus_vote({
                "vote_id": vote.vote_id,
                "request_id": vote.request_id,
                "operator_id": vote.operator_id,
                "approved": vote.approved,
                "signature": vote.signature,
                "reason": vote.reason,
                "timestamp": vote.timestamp.isoformat(),
            })

    async def verify_ledger_integrity(self) -> tuple[bool, int]:
        """Verify the integrity of the liability ledger chain."""
        return await self._ledger.verify_chain_integrity()

    async def get_ledger_stats(self) -> dict[str, Any]:
        """Get statistics from the liability ledger."""
        total = await self._ledger.count()
        blocked = await self._ledger.count("block")
        allowed = await self._ledger.count("allow")
        return {
            "total_records": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": blocked / max(total, 1),
            "cost_usage": self._cost_governor.get_usage_summary(),
        }
