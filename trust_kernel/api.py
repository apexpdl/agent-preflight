"""
Preflight Execution Firewall — Enterprise REST API.

Production-grade API with:
- Rate limiting per tenant
- Authentication middleware (API key + scoped token)
- Structured error responses
- Comprehensive health endpoint
- Prometheus metrics endpoint
- Safety snapshot generation
- Key management endpoints
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from trust_kernel.kernel import TrustKernel, TrustKernelConfig
from trust_kernel.models import (
    ActionType,
    ExecutionEnvelope,
    MutabilityClass,
    StructuredIntent,
)


def create_trustkernel_api(config: Optional[TrustKernelConfig] = None):
    """Create a FastAPI application with Preflight endpoints."""
    try:
        from fastapi import FastAPI, HTTPException, Query, Request, Response
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, PlainTextResponse
    except ImportError:
        raise ImportError(
            "FastAPI is required for the Preflight API. "
            "Install with: pip install 'agent-preflight[server]'"
        )

    from trust_kernel.multitenancy import TenantManager, RBACManager
    from trust_kernel.observability import MetricsCollector, StructuredLogger
    from trust_kernel.snapshot import SafetySnapshot

    app = FastAPI(
        title="Preflight Execution Firewall",
        description=(
            "Cryptographically verifiable, deterministic execution "
            "firewall for AI agents. Enterprise-grade safety infrastructure."
        ),
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    kernel = TrustKernel(config)
    tenant_manager = TenantManager()
    rbac = RBACManager()
    metrics = MetricsCollector()
    logger = StructuredLogger(name="preflight.api")

    # -- Rate Limiting State ---------------------------------------------------

    _rate_buckets: dict[str, list[float]] = {}

    def _check_rate_limit(tenant_id: str, rpm: int) -> bool:
        now = time.time()
        bucket = _rate_buckets.setdefault(tenant_id, [])
        # Prune entries older than 60s
        cutoff = now - 60
        _rate_buckets[tenant_id] = [t for t in bucket if t > cutoff]
        bucket = _rate_buckets[tenant_id]
        if len(bucket) >= rpm:
            return False
        bucket.append(now)
        return True

    # -- Structured Error Responses -------------------------------------------

    def _error(status: int, code: str, message: str, details: Any = None):
        body = {
            "error": {
                "code": code,
                "message": message,
                "timestamp": time.time(),
            }
        }
        if details:
            body["error"]["details"] = details
        return JSONResponse(status_code=status, content=body)

    # -- Auth Middleware -------------------------------------------------------

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Skip auth for health, docs, metrics
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json", "/redoc", "/metrics"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")
        tenant = None

        if auth_header.startswith("Bearer "):
            token_str = auth_header[7:]
            result = tenant_manager.authenticate_token(token_str)
            if result:
                tenant, token = result
                request.state.tenant = tenant
                request.state.token = token
            else:
                return _error(401, "INVALID_TOKEN", "Invalid or expired token")
        elif api_key:
            tenant = tenant_manager.authenticate_by_key(api_key)
            if tenant:
                request.state.tenant = tenant
                request.state.token = None
            else:
                return _error(401, "INVALID_API_KEY", "Invalid API key")
        else:
            # Allow unauthenticated for development
            request.state.tenant = None
            request.state.token = None

        # Rate limit check
        if tenant and not _check_rate_limit(tenant.tenant_id, tenant.rate_limit_rpm):
            logger.warning("rate_limited", tenant_id=tenant.tenant_id)
            return _error(
                429,
                "RATE_LIMITED",
                f"Rate limit exceeded ({tenant.rate_limit_rpm} rpm)",
            )

        return await call_next(request)

    @app.on_event("startup")
    async def startup():
        await kernel.initialize()
        logger.info("api_started", version="2.0.0")

    # -- Execute ---------------------------------------------------------------

    @app.post("/execute")
    async def execute_action(payload: dict[str, Any]):
        """Execute an action through the Preflight pipeline."""
        start = time.perf_counter()
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

            elapsed = (time.perf_counter() - start) * 1000
            metrics.record_action(
                verdict=result.verdict if hasattr(result, "verdict") else "allow",
                risk_score=getattr(result, "risk_score", 0.0),
                pipeline_ms=elapsed,
                tool_name=payload.get("tool_name", ""),
                agent_id=payload.get("agent_id", ""),
            )

            return JSONResponse(content=result.to_dict())
        except ValueError as exc:
            return _error(400, "VALIDATION_ERROR", str(exc))
        except Exception as exc:
            logger.error("execute_failed", error=str(exc))
            return _error(500, "INTERNAL_ERROR", "Execution pipeline failed")

    # -- Ledger ----------------------------------------------------------------

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
            return _error(404, "NOT_FOUND", "Record not found")
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

    # -- Consensus -------------------------------------------------------------

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
            return _error(400, "MISSING_FIELD", "operator_id required")

        approved = await kernel.approve_consensus(request_id, operator_id, reason)
        return {"approved": approved, "request_id": request_id}

    @app.post("/consensus/{request_id}/reject")
    async def reject_action(request_id: str, payload: dict[str, Any]):
        """Reject a pending consensus request."""
        operator_id = payload.get("operator_id", "")
        reason = payload.get("reason", "")
        if not operator_id:
            return _error(400, "MISSING_FIELD", "operator_id required")

        await kernel.reject_consensus(request_id, operator_id, reason)
        return {"rejected": True, "request_id": request_id}

    # -- Stats -----------------------------------------------------------------

    @app.get("/stats")
    async def get_stats():
        """Get execution statistics."""
        return await kernel.get_ledger_stats()

    # -- Replay ----------------------------------------------------------------

    @app.get("/replay/{action_id}")
    async def get_replay_manifest(action_id: str):
        """Get the deterministic replay manifest for an action."""
        manifest = kernel.reproducibility.export_manifest(action_id)
        if not manifest:
            return _error(404, "NOT_FOUND", "Manifest not found")
        return manifest

    # -- Cost ------------------------------------------------------------------

    @app.get("/cost")
    async def get_cost_usage():
        """Get current cost and resource usage."""
        return kernel.cost_governor.get_usage_summary()

    # -- Metrics ---------------------------------------------------------------

    @app.get("/metrics")
    async def prometheus_metrics():
        """Export Prometheus-compatible metrics."""
        return PlainTextResponse(
            content=metrics.export_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/metrics/json")
    async def metrics_json():
        """Export metrics as structured JSON."""
        return metrics.export_json()

    # -- Keys ------------------------------------------------------------------

    @app.get("/keys/public")
    async def get_public_keys():
        """Export public keys for independent verification."""
        return {"keys": kernel.crypto.export_public_keys()}

    @app.post("/keys/rotate/{role}")
    async def rotate_key(role: str):
        """Rotate a signing key for a given role."""
        if role not in ("agent", "policy", "operator"):
            return _error(400, "INVALID_ROLE", f"Unknown role: {role}")
        new_key = kernel.crypto.rotate_key(role)
        logger.info("key_rotated", role=role)
        return {"rotated": True, "key_info": new_key}

    # -- Snapshots -------------------------------------------------------------

    @app.get("/snapshot")
    async def generate_snapshot():
        """Generate a Safety Snapshot from recent activity."""
        snap = SafetySnapshot(period_label="API Generated")
        stats = await kernel.get_ledger_stats()
        if isinstance(stats, dict):
            snap.total_actions = stats.get("total", 0)
            snap.blocked_actions = stats.get("blocked", 0)
            snap.allowed_actions = stats.get("allowed", 0)
        return snap.to_dict()

    @app.get("/snapshot/html")
    async def generate_snapshot_html():
        """Generate an HTML Safety Snapshot."""
        snap = SafetySnapshot(period_label="API Generated")
        return Response(
            content=snap.generate_html(),
            media_type="text/html",
        )

    @app.get("/snapshot/badge.svg")
    async def generate_badge():
        """Generate an SVG safety badge."""
        snap = SafetySnapshot()
        return Response(
            content=snap.generate_badge_svg(),
            media_type="image/svg+xml",
        )

    # -- Health ----------------------------------------------------------------

    @app.get("/health")
    async def health():
        """Comprehensive health check."""
        ledger_ok = kernel._initialized
        ledger_integrity = True
        record_count = 0

        try:
            valid, count = await kernel.verify_ledger_integrity()
            ledger_integrity = valid
            record_count = count
        except Exception:
            ledger_integrity = False

        status = "healthy" if (ledger_ok and ledger_integrity) else "degraded"

        return {
            "status": status,
            "version": "2.0.0",
            "components": {
                "ledger": {
                    "initialized": ledger_ok,
                    "integrity": "intact" if ledger_integrity else "unknown",
                    "records": record_count,
                },
                "crypto": {
                    "algorithm": kernel.crypto.algorithm,
                    "keys_loaded": len(kernel.crypto.registry),
                },
                "metrics": {
                    "total_actions": metrics.export_json().get("counters", {}),
                },
            },
        }

    return app
