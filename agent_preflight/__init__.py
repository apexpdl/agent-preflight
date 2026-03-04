"""Agent Preflight — Autonomous Trust Fabric for AI Agents.

Predictive consequence infrastructure: intercepts agent actions,
scores risk, simulates outcomes, enforces policy, and issues
signed Action Passports before execution.
"""

__version__ = "1.0.0"

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
