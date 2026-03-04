"""
Agent-Preflight: Autonomous Trust Fabric (ATF)

A universal pre-execution governance layer for AI agents.
Intercepts tool calls, enforces structured intent, computes risk,
simulates consequences, and produces signed Action Passports.
"""

from agent_preflight.atf.models import (
    ActionEnvelope,
    StructuredIntent,
    RiskAssessment,
    MirrorResult,
    FileDelta,
    PolicyDecision,
    ActionPassport,
    SimulationResult,
    DomainSimulationResult,
    DriftInsight,
    CorrectionFeedback,
    PipelineResult,
    ExecutionMode,
)
from agent_preflight.atf.config import ATFConfig

__all__ = [
    "ActionEnvelope",
    "StructuredIntent",
    "RiskAssessment",
    "MirrorResult",
    "FileDelta",
    "PolicyDecision",
    "ActionPassport",
    "SimulationResult",
    "DomainSimulationResult",
    "DriftInsight",
    "CorrectionFeedback",
    "PipelineResult",
    "ExecutionMode",
    "ATFConfig",
]
