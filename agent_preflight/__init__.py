"""Agent Preflight — Stop your AI agent before it destroys something.

One line of code. Zero config. Your agent's actions are risk-scored,
simulated, and blocked before they touch the real world.

Quick Start:
    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()  # done. every tool call is now safe.

Or for any framework:
    from agent_preflight import Preflight
    pf = Preflight()

    @pf.intercept
    def my_tool(args):
        ...

    plan = pf.dry_run(workflow, task="description")
    print(pf.format(plan))
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
