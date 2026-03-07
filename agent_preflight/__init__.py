"""Agent Preflight — Stop your AI agent before it destroys something.

The firewall and control plane for AI agents. One line of code.
Zero config. Your agent's actions are risk-scored, simulated,
and blocked before they touch the real world.

Quick Start:
    from agent_preflight import enable_agent_firewall
    enable_agent_firewall()  # done. every tool call is now safe.

Or framework-specific:
    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()

Or zero-config:
    PREFLIGHT_AUTO=1 python my_agent.py
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


def enable_agent_firewall(
    mode: str = "safe",
    silent: bool = False,
    verbose: bool = False,
) -> list[str]:
    """Enable Preflight protection for all detected agent frameworks.

    This is the simplest possible API — one line to protect everything:

        from agent_preflight import enable_agent_firewall
        enable_agent_firewall()

    Args:
        mode: Execution mode — "safe", "balanced", "aggressive", "enterprise"
        silent: Suppress the startup banner
        verbose: Print detailed detection info

    Returns:
        List of framework names that were detected and wrapped.
    """
    from agent_preflight.auto import enable as auto_enable
    from agent_preflight.atf.config import ExecutionMode
    from agent_preflight.display import render_startup_banner

    mode_enum = ExecutionMode(mode)
    wrapped = auto_enable(mode=mode_enum, verbose=verbose)

    if not silent:
        import sys
        print(render_startup_banner(), end="", file=sys.stderr)

    return wrapped


__all__ = [
    # Top-level API
    "enable_agent_firewall",
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
