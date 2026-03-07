"""
TrustKernel data models — Pydantic-validated structures for the entire
execution pipeline. Every model enforces strict types and validation.
"""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MutabilityClass(str, enum.Enum):
    IMMUTABLE = "immutable"
    REVERSIBLE = "reversible"
    DESTRUCTIVE = "destructive"


class ActionType(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    API_CALL = "api_call"
    SHELL = "shell"
    NETWORK = "network"
    FILESYSTEM = "filesystem"


class Verdict(str, enum.Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"
    ROLLBACK = "rollback"


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Intent — structured declaration of what an agent wants to do
# ---------------------------------------------------------------------------

class StructuredIntent(BaseModel):
    """Every action must declare its intent before execution."""
    goal: str = Field(..., min_length=1)
    reasoning_summary: str = Field(..., min_length=1)
    action_type: ActionType = ActionType.EXECUTE
    target_resource: str = ""
    mutability_class: MutabilityClass = MutabilityClass.REVERSIBLE
    reversible: bool = True
    estimated_cost: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    external_dependency_count: int = Field(default=0, ge=0)
    expected_state_changes: list[str] = Field(default_factory=list)
    external_calls: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution Envelope — the universal action wrapper
# ---------------------------------------------------------------------------

class ExecutionEnvelope(BaseModel):
    """Universal wrapper for any action entering the TrustKernel pipeline."""
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    intent: StructuredIntent
    resource_targets: list[str] = Field(default_factory=list)
    privilege_level: str = Field(default="standard")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {"tool": self.tool_name, "args": self.arguments, "intent_goal": self.intent.goal},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def canonical_bytes(self) -> bytes:
        data = {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "intent_goal": self.intent.goal,
            "timestamp": self.timestamp.isoformat(),
        }
        return json.dumps(data, sort_keys=True).encode()


# ---------------------------------------------------------------------------
# State Snapshot & Diff
# ---------------------------------------------------------------------------

class StateSnapshot(BaseModel):
    """Minimal relevant state captured before/after execution."""
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    agent_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state_hash: str = ""
    entries: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        canonical = json.dumps(self.entries, sort_keys=True)
        self.state_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return self.state_hash


class StateDiff(BaseModel):
    """Comparison between predicted and actual post-state."""
    diff_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    pre_state_hash: str
    predicted_post_hash: str
    actual_post_hash: str
    field_diffs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    deviation_pct: float = 0.0
    fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    exceeds_threshold: bool = False


# ---------------------------------------------------------------------------
# Deterministic Execution Envelope (DEE)
# ---------------------------------------------------------------------------

class DeterministicExecutionEnvelope(BaseModel):
    """The complete cryptographic execution artifact for every action."""
    dee_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    agent_id: str
    tool_name: str
    intent_digest: str = ""
    pre_state_hash: str = ""
    predicted_post_hash: str = ""
    actual_post_hash: str = ""
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_bound: float = Field(default=0.1, ge=0.0, le=1.0)
    fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    rollback_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: Verdict = Verdict.ALLOW
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Signatures
    agent_signature: str = ""
    operator_signature: str = ""
    policy_signature: str = ""

    # Simulation metadata
    simulation_runs: int = 0
    simulation_failure_pct: float = 0.0

    def canonical_bytes(self) -> bytes:
        data = {
            "dee_id": self.dee_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "intent_digest": self.intent_digest,
            "pre_state_hash": self.pre_state_hash,
            "predicted_post_hash": self.predicted_post_hash,
            "risk_score": self.risk_score,
            "verdict": self.verdict.value,
            "timestamp": self.timestamp.isoformat(),
        }
        return json.dumps(data, sort_keys=True).encode()


# ---------------------------------------------------------------------------
# Liability Ledger Record
# ---------------------------------------------------------------------------

class LiabilityRecord(BaseModel):
    """Append-only tamper-proof record in the liability ledger."""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    dee_id: str = ""
    agent_id: str = ""
    operator_id: str = ""
    tool_name: str = ""
    risk_score: float = 0.0
    verdict: Verdict = Verdict.ALLOW
    pre_state_hash: str = ""
    post_state_hash: str = ""
    agent_signature: str = ""
    operator_signature: str = ""
    policy_signature: str = ""
    chain_hash: str = ""  # Hash linking to previous record
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_chain_hash(self, previous_hash: str = "") -> str:
        data = {
            "record_id": self.record_id,
            "action_id": self.action_id,
            "dee_id": self.dee_id,
            "verdict": self.verdict.value,
            "pre_state_hash": self.pre_state_hash,
            "post_state_hash": self.post_state_hash,
            "previous_hash": previous_hash,
            "timestamp": self.timestamp.isoformat(),
        }
        canonical = json.dumps(data, sort_keys=True)
        self.chain_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return self.chain_hash


# ---------------------------------------------------------------------------
# Operator Consensus
# ---------------------------------------------------------------------------

class ConsensusRequest(BaseModel):
    """Request for operator approval on irreversible actions."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    dee_id: str = ""
    agent_id: str = ""
    tool_name: str = ""
    risk_score: float = 0.0
    required_approvals: int = 1
    collected_approvals: int = 0
    status: ConsentStatus = ConsentStatus.PENDING
    expires_at: Optional[datetime] = None
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsensusVote(BaseModel):
    """A single operator's approval or rejection."""
    vote_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    operator_id: str
    approved: bool
    signature: str = ""
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

class ReplayManifest(BaseModel):
    """Everything needed to deterministically replay an action."""
    manifest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    dee_id: str = ""
    model_version: str = ""
    model_seed: int = 0
    temperature: float = 0.0
    pre_state_snapshot: dict[str, Any] = Field(default_factory=dict)
    envelope_data: dict[str, Any] = Field(default_factory=dict)
    expected_result: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Cost Budget
# ---------------------------------------------------------------------------

class CostBudget(BaseModel):
    """Cost tracking and enforcement."""
    budget_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    total_budget: float = Field(default=1000.0, ge=0.0)
    spent: float = Field(default=0.0, ge=0.0)
    remaining: Optional[float] = None
    max_single_action: float = Field(default=100.0, ge=0.0)
    token_budget: int = Field(default=1_000_000, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    api_calls_limit: int = Field(default=10_000, ge=0)
    api_calls_used: int = Field(default=0, ge=0)
    recursion_depth_limit: int = Field(default=50, ge=1)
    tool_invocation_limit: int = Field(default=1000, ge=1)
    tool_invocations_used: int = Field(default=0, ge=0)

    def model_post_init(self, __context) -> None:
        if self.remaining is None:
            self.remaining = self.total_budget - self.spent

    @property
    def budget_exhausted(self) -> bool:
        return (self.remaining or 0) <= 0 or self.tokens_used >= self.token_budget

    def can_afford(self, cost: float) -> bool:
        rem = self.remaining if self.remaining is not None else self.total_budget
        return cost <= rem and cost <= self.max_single_action

    def charge(self, cost: float, tokens: int = 0) -> bool:
        if not self.can_afford(cost):
            return False
        self.spent += cost
        self.remaining = self.total_budget - self.spent
        self.tokens_used += tokens
        self.api_calls_used += 1
        self.tool_invocations_used += 1
        return True
