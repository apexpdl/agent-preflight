"""
ATF Gateway — FastAPI-powered interception layer.

The central orchestrator that ties together all ATF components:
Intent Compiler → Risk Engine → Simulation → Drift → Policy → Mirror → Passport

Exposes REST endpoints and an async internal API.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.database import ATFDatabase
from agent_preflight.atf.drift import DriftIntelligenceEngine
from agent_preflight.atf.feedback import FeedbackGenerator
from agent_preflight.atf.intent_compiler import IntentCompiler
from agent_preflight.atf.mirror_world import MirrorWorld
from agent_preflight.atf.models import (
    ActionEnvelope,
    PipelineResult,
    Verdict,
)
from agent_preflight.atf.passport import PassportAuthority
from agent_preflight.atf.policy_v2 import YAMLPolicyEngine
from agent_preflight.atf.risk_engine import RiskEngine
from agent_preflight.atf.risk_memory import RiskMemory
from agent_preflight.atf.simulation import SimulationEngine


class ATFGateway:
    """Central gateway that orchestrates the full ATF pipeline.

    Usage:
        gateway = ATFGateway(config)
        await gateway.initialize()
        result = await gateway.intercept_and_execute(envelope)
    """

    def __init__(self, config: Optional[ATFConfig] = None):
        self.config = config or ATFConfig()
        self.db = ATFDatabase(self.config.database_path)
        self.risk_engine = RiskEngine(
            mirror_threshold=self.config.risk_threshold_mirror
        )
        self.intent_compiler = IntentCompiler()
        self.mirror_world = MirrorWorld(
            timeout_seconds=self.config.mirror_timeout_seconds
        )
        self.passport_authority = PassportAuthority(self.config.passport_secret_key)
        self.simulation_engine = SimulationEngine()
        self.policy_engine = YAMLPolicyEngine()
        self.drift_engine: Optional[DriftIntelligenceEngine] = None
        self.feedback_generator = FeedbackGenerator()
        self.risk_memory = RiskMemory()
        self._tool_registry: dict[str, Callable] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database and engines."""
        await self.db.initialize()
        self.drift_engine = DriftIntelligenceEngine(
            self.db, self.config.drift_anomaly_threshold
        )
        if self.config.policy_file and self.config.policy_file.exists():
            self.policy_engine.load_file(self.config.policy_file)
        self._initialized = True

    def register_tool(self, name: str, fn: Callable) -> None:
        """Register a tool function for mirror/real execution."""
        self._tool_registry[name] = fn

    def register_plugins(self, plugins: list) -> None:
        """Register simulation plugins."""
        for plugin_cls in plugins:
            if callable(plugin_cls) and not hasattr(plugin_cls, 'name'):
                # It's a class, instantiate it
                self.simulation_engine.register_plugin(plugin_cls())
            else:
                self.simulation_engine.register_plugin(plugin_cls)

    async def intercept_and_execute(
        self,
        envelope: ActionEnvelope,
        tool_fn: Optional[Callable] = None,
    ) -> PipelineResult:
        """Run the full ATF pipeline for an action.

        Pipeline stages:
        1. Intent compilation
        2. Risk scoring
        3. Drift analysis (if enabled)
        4. Simulation (if risk warrants it)
        5. Policy evaluation
        6. Mirror execution (if risk warrants it)
        7. Verdict determination
        8. Passport issuance
        9. Logging
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        # 1. Compile intent
        compiled = await self.intent_compiler.compile(envelope)

        # 2. Drift analysis
        drift_similarity = 0.0
        drift_insight = None
        if self.config.drift_enabled and self.drift_engine:
            drift_insight = await self.drift_engine.analyze(
                envelope.fingerprint(), compiled.embedding, 0.0
            )
            drift_similarity = drift_insight.similarity_score

        # 2b. Risk Memory recall — learn from past decisions
        memory_recall = self.risk_memory.recall(
            envelope.tool_name, envelope.arguments
        )
        if memory_recall.memory_flags:
            drift_similarity = max(
                drift_similarity,
                drift_similarity + memory_recall.risk_adjustment,
            )

        # 3. Risk scoring (informed by memory + drift)
        risk = await self.risk_engine.assess(envelope, drift_similarity)

        # 4. Simulation (if configured and risk warrants it)
        simulation = None
        if (
            self.config.simulation_enabled
            and risk.score >= self.config.risk_threshold_mirror * 0.6
        ):
            simulation = await self.simulation_engine.run_rollouts(
                envelope, n=self.config.simulation_rollouts
            )

        # 5. Policy evaluation
        policy = self.policy_engine.evaluate(envelope)

        # 6. Mirror execution (if risk warrants it)
        mirror = None
        if (
            self.config.mirror_enabled
            and risk.requires_mirror
            and policy.allow
        ):
            fn = tool_fn or self._tool_registry.get(envelope.tool_name)
            mirror = await self.mirror_world.execute(envelope, fn)

        # 7. Determine verdict
        verdict = self._determine_verdict(risk, policy, mirror, simulation)

        # 8. Generate human summary
        human_summary = self.feedback_generator.generate_human_summary(
            envelope, risk, simulation
        )

        # 9. Generate correction feedback if blocked
        correction = None
        if verdict == Verdict.BLOCK:
            correction = self.feedback_generator.generate(
                envelope, risk, policy, mirror, simulation
            )

        # 10. Issue passport
        passport = None
        if verdict in (Verdict.ALLOW, Verdict.WARN):
            passport = self.passport_authority.issue(
                envelope=envelope,
                intent_hash=compiled.intent_hash,
                risk=risk,
                policy=policy,
                verdict=verdict,
                simulation=simulation,
                drift=drift_insight,
                mirror=mirror,
                human_summary=human_summary,
            )
            await self.db.store_passport(
                self.passport_authority.passport_to_db_record(passport)
            )

        # 11. Store risk assessment
        await self.db.store_risk(envelope.action_id, risk.model_dump())

        # 12. Record in Risk Memory (Preflight learns from every decision)
        self.risk_memory.record(
            tool_name=envelope.tool_name,
            arguments=envelope.arguments,
            risk_score=risk.score,
            verdict=verdict.value,
            flags=risk.flags,
            agent_id=envelope.agent_id,
        )

        # 13. Record drift outcome
        if self.drift_engine:
            await self.drift_engine.record_outcome(
                fingerprint=envelope.fingerprint(),
                embedding=compiled.embedding,
                risk_score=risk.score,
                outcome=verdict.value,
                is_failure=verdict == Verdict.BLOCK,
                agent_id=envelope.agent_id,
            )

        elapsed = (time.perf_counter() - start) * 1000

        # 14. Build pipeline result
        result = PipelineResult(
            action_id=envelope.action_id,
            verdict=verdict,
            risk_assessment=risk,
            simulation_result=simulation,
            drift_insight=drift_insight,
            mirror_result=mirror,
            policy_decision=policy,
            passport=passport,
            correction=correction,
            human_summary=human_summary,
            total_pipeline_time_ms=round(elapsed, 3),
        )

        # 15. Log pipeline result
        await self.db.store_pipeline_log({
            "action_id": envelope.action_id,
            "agent_id": envelope.agent_id,
            "tool_name": envelope.tool_name,
            "verdict": verdict.value,
            "risk_score": risk.score,
            "pipeline_time_ms": result.total_pipeline_time_ms,
            "full_result": result.to_agent_response(),
        })

        return result

    def _determine_verdict(
        self,
        risk,
        policy,
        mirror,
        simulation,
    ) -> Verdict:
        """Determine final verdict from all pipeline outputs."""
        # Policy blocks override everything
        if not policy.allow:
            return Verdict.BLOCK

        # Policy requires approval
        if policy.requires_approval:
            return Verdict.REQUIRE_APPROVAL

        # Mirror mismatch blocks
        if mirror and not mirror.matches_intent:
            return Verdict.BLOCK

        # Critical risk blocks
        if risk.score >= self.config.risk_threshold_block:
            return Verdict.BLOCK

        # High simulation failure blocks
        if simulation and simulation.failure_probability > 0.6:
            return Verdict.BLOCK

        # Moderate risk warns
        if risk.score >= self.config.risk_threshold_mirror:
            return Verdict.WARN

        # Moderate simulation risk warns
        if simulation and simulation.failure_probability > 0.3:
            return Verdict.WARN

        return Verdict.ALLOW


def create_fastapi_app(config: Optional[ATFConfig] = None):
    """Create a FastAPI application with ATF gateway endpoints."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError(
            "FastAPI is required for the ATF gateway. "
            "Install with: pip install agent-preflight[server]"
        )

    app = FastAPI(
        title="Agent Preflight — Autonomous Trust Fabric",
        description="Universal pre-execution governance layer for AI agents",
        version="1.0.0",
    )
    gateway = ATFGateway(config)

    @app.on_event("startup")
    async def startup():
        await gateway.initialize()
        # Register default simulation plugins
        from agent_preflight.atf.plugins import ALL_PLUGINS
        gateway.register_plugins([p() for p in ALL_PLUGINS])

    @app.post("/execute")
    async def execute_action(payload: dict):
        """Intercept and evaluate an agent action."""
        try:
            intent_data = payload.get("intent", {})
            from agent_preflight.atf.models import StructuredIntent
            intent = StructuredIntent(**intent_data)

            envelope = ActionEnvelope(
                agent_id=payload.get("agent_id", "unknown"),
                tool_name=payload.get("tool_name", "unknown"),
                arguments=payload.get("arguments", {}),
                intent=intent,
                resource_targets=payload.get("resource_targets", []),
                privilege_level=payload.get("privilege_level", "standard"),
                metadata=payload.get("metadata", {}),
            )

            result = await gateway.intercept_and_execute(envelope)
            return JSONResponse(content=result.to_agent_response())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/passports")
    async def list_passports(
        agent_id: Optional[str] = None,
        limit: int = 50,
        min_risk: Optional[float] = None,
    ):
        """List recent action passports."""
        passports = await gateway.db.get_passports(agent_id, limit, min_risk)
        return {"passports": passports}

    @app.get("/stats")
    async def get_stats():
        """Get pipeline statistics."""
        stats = await gateway.db.get_stats()
        return stats

    @app.get("/health")
    async def health():
        return {"status": "healthy", "mode": gateway.config.mode.value}

    return app
