"""
TrustKernel — Enterprise-grade cryptographically verifiable AI execution layer.

Deterministic, auditable, legally traceable execution for all AI agent actions.
The structural trust substrate for autonomous AI systems.

Quick Start:
    from trust_kernel import TrustKernel
    kernel = TrustKernel()
    await kernel.initialize()
    result = await kernel.execute(envelope)
"""

__version__ = "1.0.0"

from trust_kernel.models import (
    ExecutionEnvelope,
    DeterministicExecutionEnvelope,
    StateSnapshot,
    StateDiff,
    LiabilityRecord,
    ConsensusRequest,
    ConsensusVote,
    ReplayManifest,
    CostBudget,
)
from trust_kernel.kernel import TrustKernel
from trust_kernel.crypto import CryptoProvider
from trust_kernel.planner import DeterministicPlanner, ExecutionDAG
from trust_kernel.state_engine import StateEngine
from trust_kernel.verifier import ExecutionVerifier
from trust_kernel.rollback import RollbackController
from trust_kernel.ledger import LiabilityLedger
from trust_kernel.consensus import OperatorConsensus
from trust_kernel.cost_governor import CostGovernor
from trust_kernel.reproducibility import ReproducibilityEngine

__all__ = [
    "TrustKernel",
    "CryptoProvider",
    "DeterministicPlanner",
    "ExecutionDAG",
    "StateEngine",
    "ExecutionVerifier",
    "RollbackController",
    "LiabilityLedger",
    "OperatorConsensus",
    "CostGovernor",
    "ReproducibilityEngine",
    "ExecutionEnvelope",
    "DeterministicExecutionEnvelope",
    "StateSnapshot",
    "StateDiff",
    "LiabilityRecord",
    "ConsensusRequest",
    "ConsensusVote",
    "ReplayManifest",
    "CostBudget",
]
