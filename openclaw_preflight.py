"""
openclaw-preflight — Zero-config safety for OpenClaw agents.

Stop your AI agent before it deletes your database.

Usage:
    import openclaw_preflight
    openclaw_preflight.enable()

That's it. Every OpenClaw tool call now goes through Preflight's
risk engine. Low-risk actions pass silently. High-risk actions
get blocked with correction suggestions.

Advanced:
    import openclaw_preflight

    # Custom mode
    openclaw_preflight.enable(mode="enterprise")

    # With callbacks
    openclaw_preflight.enable(
        on_block=lambda r: print(f"BLOCKED: {r.human_summary}"),
        on_warn=lambda r: print(f"WARNING: {r.human_summary}"),
    )

    # Wrap a specific executor
    safe_executor = openclaw_preflight.wrap(my_executor)
"""

from agent_preflight.integrations.openclaw import (
    OpenClawPreflight,
    enable_preflight,
    get_preflight,
    auto_enable,
)
from agent_preflight.atf.config import ExecutionMode


def enable(mode="safe", on_block=None, on_warn=None, silent=True):
    """Enable Preflight for OpenClaw. One line. Zero config.

    Args:
        mode: "safe" (default), "balanced", "aggressive", "enterprise"
        on_block: callback when action is blocked
        on_warn: callback when action triggers warning
        silent: True = low-risk actions pass without output

    Returns:
        OpenClawPreflight instance
    """
    exec_mode = ExecutionMode(mode)
    return enable_preflight(
        mode=exec_mode,
        on_block=on_block,
        on_warn=on_warn,
        silent=silent,
    )


def wrap(executor):
    """Wrap any tool executor with Preflight governance.

    Args:
        executor: The function that executes tools

    Returns:
        Wrapped executor with safety checks
    """
    pf = get_preflight()
    if pf is None:
        pf = enable()
    return pf.wrap_sync_executor(executor)


def wrap_async(executor):
    """Wrap an async tool executor with Preflight governance."""
    pf = get_preflight()
    if pf is None:
        pf = enable()
    return pf.wrap_executor(executor)


def status():
    """Check if Preflight is active and get stats."""
    pf = get_preflight()
    if pf is None:
        return {"active": False}
    return {"active": True, **pf.stats}


__all__ = ["enable", "wrap", "wrap_async", "status", "auto_enable"]
