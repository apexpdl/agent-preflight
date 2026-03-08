from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.models import (
    ActionEnvelope,
    ActionType,
    StructuredIntent,
    Verdict,
)

from demo.backend.config import DemoConfig

# ---------------------------------------------------------------------------
# Configuration & logging
# ---------------------------------------------------------------------------

config = DemoConfig()

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(message)s",
)
logger = logging.getLogger("preflight.demo")


def _log_json(level: str, **fields: Any) -> None:
    fields["level"] = level
    fields["ts"] = time.time()
    getattr(logger, level)(json.dumps(fields, default=str))


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SimulateActionType(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    SHELL = "shell"
    API_CALL = "api_call"


_ACTION_TYPE_MAP: dict[SimulateActionType, ActionType] = {
    SimulateActionType.READ: ActionType.READ,
    SimulateActionType.WRITE: ActionType.WRITE,
    SimulateActionType.DELETE: ActionType.DELETE,
    SimulateActionType.EXECUTE: ActionType.EXECUTE,
    SimulateActionType.NETWORK: ActionType.NETWORK,
    SimulateActionType.SHELL: ActionType.SHELL,
    SimulateActionType.API_CALL: ActionType.API_CALL,
}


class SimulateRequest(BaseModel):
    actor: str = Field(..., min_length=1, max_length=100)
    action_type: SimulateActionType
    resource: str = Field(..., min_length=1, max_length=500)
    payload: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None

    @field_validator("actor", "resource")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class SimulateResponse(BaseModel):
    action_id: str
    risk_score: float
    risk_factors: list[str]
    decision: str
    simulation_summary: dict[str, Any]
    passport: Optional[dict[str, Any]]
    pipeline_time_ms: float
    human_summary: str


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class _RateLimiter:
    def __init__(self, rpm: int):
        self._rpm = rpm
        self._window = 60.0
        self._buckets: dict[str, deque[float]] = {}

    def check(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(key, deque())
        while bucket and bucket[0] <= now - self._window:
            bucket.popleft()
        if len(bucket) >= self._rpm:
            return False
        bucket.append(now)
        return True


_rate_limiter = _RateLimiter(config.rate_limit_rpm)

# ---------------------------------------------------------------------------
# In-memory history
# ---------------------------------------------------------------------------

_history: deque[dict[str, Any]] = deque(maxlen=100)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Preflight Demo API",
    version="0.1.0",
    docs_url="/docs" if config.demo_mode else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_gateway: Optional[ATFGateway] = None


@app.on_event("startup")
async def _startup() -> None:
    global _gateway

    atf_config = ATFConfig.for_mode(
        config.atf_mode,
        passport_secret_key=config.atf_passport_secret,
    )
    _gateway = ATFGateway(atf_config)
    await _gateway.initialize()

    from agent_preflight.atf.plugins import ALL_PLUGINS
    _gateway.register_plugins([p() for p in ALL_PLUGINS])

    _log_json("info", event="startup", mode=config.atf_mode.value, demo=config.demo_mode)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def _request_pipeline(request: Request, call_next) -> Response:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.check(client_ip):
        _log_json("warning", event="rate_limited", ip=client_ip, request_id=request_id)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > config.max_payload_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload exceeds {config.max_payload_bytes} byte limit."},
            )

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    response.headers["X-Request-ID"] = request_id
    _log_json(
        "info",
        event="request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=elapsed_ms,
        request_id=request_id,
    )
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "demo_mode": config.demo_mode,
        "atf_mode": config.atf_mode.value,
    }


@app.get("/history")
async def history() -> dict[str, Any]:
    return {"simulations": list(_history)}


@app.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest, request: Request) -> SimulateResponse:
    if _gateway is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized.")

    request_id = getattr(request.state, "request_id", "unknown")

    intent = _build_intent(req)
    envelope = ActionEnvelope(
        agent_id=req.actor,
        tool_name=f"demo.{req.action_type.value}",
        action_type=_ACTION_TYPE_MAP[req.action_type],
        arguments=req.payload or {},
        intent=intent,
        resource_targets=[req.resource],
        metadata={"source": "demo", "request_id": request_id},
    )

    try:
        result = await _gateway.intercept_and_execute(envelope)
    except Exception as exc:
        _log_json("error", event="pipeline_error", error=str(exc), request_id=request_id)
        raise HTTPException(status_code=500, detail="Simulation pipeline failed.")

    decision = _verdict_to_decision(result.verdict)

    simulation_summary: dict[str, Any] = {}
    if result.simulation_result:
        sim = result.simulation_result
        simulation_summary = {
            "failure_probability": sim.failure_probability,
            "cascade_probability": sim.cascade_probability,
            "volatility_score": sim.volatility_score,
            "rollout_count": sim.rollout_count,
            "confidence_interval": list(sim.confidence_interval),
        }

    passport_data: Optional[dict[str, Any]] = None
    if result.passport:
        passport_data = {
            "passport_id": result.passport.passport_id,
            "verdict": result.passport.verdict.value,
            "risk_score": result.passport.risk_score,
            "timestamp": result.passport.timestamp.isoformat(),
            "signature": result.passport.signature,
        }

    response = SimulateResponse(
        action_id=result.action_id,
        risk_score=result.risk_assessment.score,
        risk_factors=result.risk_assessment.flags,
        decision=decision,
        simulation_summary=simulation_summary,
        passport=passport_data,
        pipeline_time_ms=result.total_pipeline_time_ms,
        human_summary=result.human_summary,
    )

    _history.append({
        "action_id": response.action_id,
        "actor": req.actor,
        "action_type": req.action_type.value,
        "resource": req.resource,
        "decision": decision,
        "risk_score": response.risk_score,
        "pipeline_time_ms": response.pipeline_time_ms,
        "timestamp": time.time(),
    })

    _log_json(
        "info",
        event="simulate",
        action_id=response.action_id,
        actor=req.actor,
        action_type=req.action_type.value,
        decision=decision,
        risk_score=response.risk_score,
        request_id=request_id,
    )

    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_intent(req: SimulateRequest) -> StructuredIntent:
    ctx = req.context or {}
    goal = ctx.get("goal", f"{req.action_type.value} on {req.resource}")
    reasoning = ctx.get("reasoning", f"Agent '{req.actor}' requested {req.action_type.value} access to {req.resource}")

    irreversible = req.action_type in (SimulateActionType.DELETE, SimulateActionType.EXECUTE)

    external_calls: list[str] = []
    if req.action_type in (SimulateActionType.NETWORK, SimulateActionType.API_CALL):
        external_calls.append(req.resource)

    expected_changes: list[str] = []
    if req.action_type == SimulateActionType.WRITE:
        expected_changes.append(f"modify:{req.resource}")
    elif req.action_type == SimulateActionType.DELETE:
        expected_changes.append(f"delete:{req.resource}")

    return StructuredIntent(
        goal=goal,
        reasoning_summary=reasoning,
        expected_state_changes=expected_changes,
        external_calls=external_calls,
        irreversible=irreversible,
        confidence=ctx.get("confidence", 0.5),
    )


def _verdict_to_decision(verdict: Verdict) -> str:
    mapping = {
        Verdict.ALLOW: "allow",
        Verdict.WARN: "warn",
        Verdict.BLOCK: "block",
        Verdict.REQUIRE_APPROVAL: "block",
    }
    return mapping.get(verdict, "block")
