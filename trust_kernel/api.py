"""
TrustKernel REST API — FastAPI endpoints for enterprise integration.

Provides endpoints for:
- /execute — evaluate & approve actions
- /passports — fetch DEEs and signed passports
- /ledger — query the liability ledger
- /consensus — manage operator approvals
- /stats — risk & execution analytics
- /replay — reproducibility manifests
- /health — system health check
"""

from __future__ import annotations

import json
from typing import Any, Optional

from trust_kernel.kernel import TrustKernel, TrustKernelConfig
from trust_kernel.models import (
    ActionType,
    ExecutionEnvelope,
    MutabilityClass,
    StructuredIntent,
)


def create_trustkernel_api(config: Optional[TrustKernelConfig] = None):
    """Create a FastAPI application with TrustKernel endpoints."""
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, PlainTextResponse
    except ImportError:
        raise ImportError(
            "FastAPI is required for the TrustKernel API. "
            "Install with: pip install 'agent-preflight[server]'"
        )

    app = FastAPI(
        title="TrustKernel — Enterprise AI Execution Layer",
        description=(
            "Cryptographically verifiable, deterministic execution "
            "substrate for AI agents. The Git for AI state mutations."
        ),
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    kernel = TrustKernel(config)

    @app.on_event("startup")
    async def startup():
        await kernel.initialize()

    # -- Execute -----------------------------------------------------------

    @app.post("/execute")
    async def execute_action(payload: dict[str, Any]):
        """Execute an action through the TrustKernel pipeline.

        Returns the full DEE with signatures, verification result,
        and execution DAG.
        """
        try:
            intent_data = payload.get("intent", {})
            intent = StructuredIntent(
                goal=intent_data.get("goal", ""),
                reasoning_summary=intent_data.get("reasoning_summary", ""),
                action_type=ActionType(intent_data.get("action_type", "execute")),
                target_resource=intent_data.get("target_resource", ""),
                mutability_class=MutabilityClass(
                    intent_data.get("mutability_class", "reversible")
                ),
                reversible=intent_data.get("reversible", True),
                estimated_cost=intent_data.get("estimated_cost", 0.0),
                confidence=intent_data.get("confidence", 0.5),
                external_dependency_count=intent_data.get("external_dependency_count", 0),
                expected_state_changes=intent_data.get("expected_state_changes", []),
                external_calls=intent_data.get("external_calls", []),
            )

            envelope = ExecutionEnvelope(
                agent_id=payload.get("agent_id", "unknown"),
                tool_name=payload.get("tool_name", "unknown"),
                arguments=payload.get("arguments", {}),
                intent=intent,
                resource_targets=payload.get("resource_targets", []),
                privilege_level=payload.get("privilege_level", "standard"),
                metadata=payload.get("metadata", {}),
            )

            result = await kernel.execute(
                envelope,
                pre_state=payload.get("pre_state"),
                risk_score=payload.get("risk_score"),
                operator_consent=payload.get("operator_consent", False),
            )

            return JSONResponse(content=result.to_dict())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # -- Ledger ------------------------------------------------------------

    @app.get("/ledger")
    async def query_ledger(
        agent_id: Optional[str] = None,
        verdict: Optional[str] = None,
        min_risk: Optional[float] = None,
        max_risk: Optional[float] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = Query(default=100, le=10000),
    ):
        """Query the liability ledger with filters."""
        records = await kernel.ledger.query(
            agent_id=agent_id,
            verdict=verdict,
            min_risk=min_risk,
            max_risk=max_risk,
            since=since,
            until=until,
            limit=limit,
        )
        return {"records": records, "count": len(records)}

    @app.get("/ledger/{record_id}")
    async def get_ledger_record(record_id: str):
        """Get a single ledger record."""
        record = await kernel.ledger.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        return record

    @app.get("/ledger/export/json")
    async def export_ledger_json(limit: int = Query(default=10000, le=100000)):
        """Export ledger as JSON for auditors."""
        data = await kernel.ledger.export_json(limit=limit)
        return PlainTextResponse(content=data, media_type="application/json")

    @app.get("/ledger/export/csv")
    async def export_ledger_csv(limit: int = Query(default=10000, le=100000)):
        """Export ledger as CSV."""
        data = await kernel.ledger.export_csv(limit=limit)
        return PlainTextResponse(content=data, media_type="text/csv")

    @app.get("/ledger/verify")
    async def verify_ledger():
        """Verify the integrity of the liability ledger chain."""
        valid, count = await kernel.verify_ledger_integrity()
        return {
            "chain_valid": valid,
            "verified_records": count,
            "status": "intact" if valid else "tampered",
        }

    # -- Consensus ---------------------------------------------------------

    @app.get("/consensus/pending")
    async def get_pending_approvals():
        """Get all pending consensus requests."""
        requests = kernel.consensus.get_pending_requests()
        return {
            "pending": [
                kernel.consensus.get_request_summary(r.request_id)
                for r in requests
            ]
        }

    @app.post("/consensus/{request_id}/approve")
    async def approve_action(request_id: str, payload: dict[str, Any]):
        """Approve a pending consensus request."""
        operator_id = payload.get("operator_id", "")
        reason = payload.get("reason", "")
        if not operator_id:
            raise HTTPException(status_code=400, detail="operator_id required")

        approved = await kernel.approve_consensus(request_id, operator_id, reason)
        return {"approved": approved, "request_id": request_id}

    @app.post("/consensus/{request_id}/reject")
    async def reject_action(request_id: str, payload: dict[str, Any]):
        """Reject a pending consensus request."""
        operator_id = payload.get("operator_id", "")
        reason = payload.get("reason", "")
        if not operator_id:
            raise HTTPException(status_code=400, detail="operator_id required")

        await kernel.reject_consensus(request_id, operator_id, reason)
        return {"rejected": True, "request_id": request_id}

    # -- Stats -------------------------------------------------------------

    @app.get("/stats")
    async def get_stats():
        """Get TrustKernel execution statistics."""
        return await kernel.get_ledger_stats()

    # -- Replay ------------------------------------------------------------

    @app.get("/replay/{action_id}")
    async def get_replay_manifest(action_id: str):
        """Get the deterministic replay manifest for an action."""
        manifest = kernel.reproducibility.export_manifest(action_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="Manifest not found")
        return manifest

    # -- Cost --------------------------------------------------------------

    @app.get("/cost")
    async def get_cost_usage():
        """Get current cost and resource usage."""
        return kernel.cost_governor.get_usage_summary()

    # -- Health ------------------------------------------------------------

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "ledger_initialized": kernel._initialized,
        }

    return app
