"""
Pydantic models for the Autonomous Trust Fabric.

Every data structure in the ATF pipeline is defined here with strict
type enforcement, validation, and serialization support.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExecutionMode(str, enum.Enum):
    """Operating mode controlling risk thresholds and behaviour."""
    SAFE = "safe"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    ENTERPRISE = "enterprise"


class Verdict(str, enum.Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class ActionType(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    SHELL = "shell"
    FILESYSTEM = "filesystem"
    API_CALL = "api_call"


# ---------------------------------------------------------------------------
# Structured Intent
# ---------------------------------------------------------------------------

class StructuredIntent(BaseModel):
    """Declared intent that must accompany every action request."""
    goal: str = Field(..., min_length=1, description="What the action aims to achieve")
    reasoning_summary: str = Field(..., min_length=1, description="Why this action is needed")
    expected_state_changes: list[str] = Field(default_factory=list)
    external_calls: list[str] = Field(default_factory=list)
    irreversible: bool = False
    estimated_cost: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Action Envelope
# ---------------------------------------------------------------------------

class ActionEnvelope(BaseModel):
    """Universal wrapper for any action flowing through the ATF pipeline."""
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    action_type: ActionType = ActionType.EXECUTE
    arguments: dict[str, Any] = Field(default_factory=dict)
    intent: StructuredIntent
    resource_targets: list[str] = Field(default_factory=list)
    privilege_level: str = Field(default="standard")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic hash of the action for drift comparison."""
        canonical = json.dumps(
            {"tool": self.tool_name, "args": self.arguments, "intent_goal": self.intent.goal},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Risk Assessment
# ---------------------------------------------------------------------------

class RiskAssessment(BaseModel):
    """Output of the Risk Engine."""
    score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    requires_mirror: bool = False
    breakdown: dict[str, float] = Field(default_factory=dict)
    computation_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Mirror World
# ---------------------------------------------------------------------------

class FileDelta(BaseModel):
    """Single file change detected in mirror execution."""
    path: str
    action: str  # created, modified, deleted
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    size_delta_bytes: int = 0


class MirrorResult(BaseModel):
    """Output of Mirror World sandbox execution."""
    state_delta: list[FileDelta] = Field(default_factory=list)
    external_attempts: list[str] = Field(default_factory=list)
    permission_violations: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    matches_intent: bool = True
    execution_time_ms: float = 0.0
    mismatch_details: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy Decision
# ---------------------------------------------------------------------------

class PolicyViolation(BaseModel):
    rule_name: str
    description: str
    severity: str = "medium"


class PolicyDecision(BaseModel):
    """Output of the Policy Engine."""
    allow: bool = True
    requires_approval: bool = False
    violations: list[PolicyViolation] = Field(default_factory=list)
    evaluated_rules: int = 0
    matched_rules: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class DomainSimulationResult(BaseModel):
    """Result from a single simulation plugin."""
    plugin_name: str
    failure_detected: bool = False
    failure_description: str = ""
    cascade_detected: bool = False
    resource_impact: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    """Aggregate result from the Probabilistic Simulation Engine."""
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    cascade_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    resource_spike_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    volatility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    rollout_count: int = 0
    domain_results: list[DomainSimulationResult] = Field(default_factory=list)
    total_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Drift Intelligence
# ---------------------------------------------------------------------------

class DriftInsight(BaseModel):
    """Output of the Drift Intelligence Engine."""
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    similar_actions: list[str] = Field(default_factory=list)
    is_anomalous: bool = False


# ---------------------------------------------------------------------------
# Action Passport
# ---------------------------------------------------------------------------

class ActionPassport(BaseModel):
    """Signed, tamper-proof audit artifact for every executed action."""
    passport_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    agent_id: str
    intent_hash: str
    tool_name: str
    risk_score: float
    simulation_risk: Optional[float] = None
    drift_score: Optional[float] = None
    policy_status: str = "approved"
    mirror_executed: bool = False
    mirror_matched: Optional[bool] = None
    verdict: Verdict = Verdict.ALLOW
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    human_summary: str = ""
    signature: str = ""

    def sign(self, secret_key: str) -> None:
        """Compute HMAC-SHA256 signature over canonical passport data."""
        canonical = json.dumps(
            {
                "passport_id": self.passport_id,
                "action_id": self.action_id,
                "agent_id": self.agent_id,
                "intent_hash": self.intent_hash,
                "risk_score": self.risk_score,
                "policy_status": self.policy_status,
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        )
        self.signature = hmac.new(
            secret_key.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()

    def verify(self, secret_key: str) -> bool:
        """Verify the passport signature is valid."""
        saved = self.signature
        self.sign(secret_key)
        valid = hmac.compare_digest(saved, self.signature)
        if not valid:
            self.signature = saved
        return valid


# ---------------------------------------------------------------------------
# Correction Feedback
# ---------------------------------------------------------------------------

class CorrectionFeedback(BaseModel):
    """Structured feedback returned to agents when actions are blocked."""
    declared_goal: str
    actual_result: str
    violations: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    rewrite_hints: list[str] = Field(default_factory=list)
    blocked: bool = True


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    """Complete output of the ATF pipeline for a single action."""
    action_id: str
    verdict: Verdict
    risk_assessment: RiskAssessment
    simulation_result: Optional[SimulationResult] = None
    drift_insight: Optional[DriftInsight] = None
    mirror_result: Optional[MirrorResult] = None
    policy_decision: PolicyDecision
    passport: Optional[ActionPassport] = None
    correction: Optional[CorrectionFeedback] = None
    human_summary: str = ""
    total_pipeline_time_ms: float = 0.0

    def to_agent_response(self) -> dict[str, Any]:
        """Format as the structured JSON agents consume."""
        resp: dict[str, Any] = {
            "verdict": self.verdict.value,
            "risk_score": self.risk_assessment.score,
            "flags": self.risk_assessment.flags,
            "human_summary": self.human_summary,
            "pipeline_time_ms": self.total_pipeline_time_ms,
        }
        if self.simulation_result:
            resp["failure_probability"] = self.simulation_result.failure_probability
            resp["volatility_index"] = self.simulation_result.volatility_score
            resp["cascade_risk"] = self.simulation_result.cascade_probability
            resp["confidence_interval"] = list(self.simulation_result.confidence_interval)
        if self.passport:
            resp["passport_id"] = self.passport.passport_id
        if self.correction:
            resp["correction"] = self.correction.model_dump()
        return resp
