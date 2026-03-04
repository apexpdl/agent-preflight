"""Agent Preflight - Preview and validate AI agent actions before execution."""

__version__ = "0.2.0"

from agent_preflight.core import Preflight
from agent_preflight.models import (
    Plan,
    ActionCapture,
    RiskLevel,
    Reversibility,
    ActionType,
    DependencyGraph,
)
from agent_preflight.renderer import render, render_plain
from agent_preflight.policy import Policy, PolicyEngine, PolicyResult, PolicyViolation
from agent_preflight.audit import AuditLog, AuditEntry
from agent_preflight.semantic import SemanticAnalyzer, SemanticAnalysis

__all__ = [
    # Core
    "Preflight",
    "Plan",
    "ActionCapture",
    "RiskLevel",
    "Reversibility",
    "ActionType",
    "DependencyGraph",
    # Rendering
    "render",
    "render_plain",
    # Policy engine
    "Policy",
    "PolicyEngine",
    "PolicyResult",
    "PolicyViolation",
    # Audit
    "AuditLog",
    "AuditEntry",
    # Semantic analysis
    "SemanticAnalyzer",
    "SemanticAnalysis",
]
