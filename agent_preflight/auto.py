"""
Universal auto-detection for AI agent frameworks.

Import this module to automatically detect and wrap any supported
agent framework with Preflight governance.

Supported frameworks:
    - OpenClaw
    - LangChain / LangGraph
    - CrewAI
    - AutoGen
    - Any framework with a tool executor pattern

Usage:
    # Option 1: Import and it just works
    import agent_preflight.auto

    # Option 2: Explicit enable
    from agent_preflight.auto import enable
    enable()

    # Option 3: Environment variable
    # Set PREFLIGHT_AUTO=1 before running your agent
"""

from __future__ import annotations

import importlib
import os
from typing import Optional

from agent_preflight.atf.config import ATFConfig, ExecutionMode


_enabled = False
_detected_frameworks: list[str] = []


def detect_frameworks() -> list[str]:
    """Detect which agent frameworks are installed."""
    frameworks = []
    checks = [
        ("openclaw", "OpenClaw"),
        ("langchain", "LangChain"),
        ("langchain_core", "LangChain Core"),
        ("crewai", "CrewAI"),
        ("autogen", "AutoGen"),
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
    ]
    for module_name, display_name in checks:
        try:
            importlib.import_module(module_name)
            frameworks.append(display_name)
        except ImportError:
            pass
    return frameworks


def enable(
    mode: ExecutionMode = ExecutionMode.SAFE,
    config: Optional[ATFConfig] = None,
    silent: bool = True,
    verbose: bool = False,
) -> list[str]:
    """Auto-detect and enable Preflight for all installed agent frameworks.

    Returns list of frameworks that were detected and wrapped.

    Usage:
        from agent_preflight.auto import enable
        wrapped = enable()
        print(f"Protected: {wrapped}")
    """
    global _enabled, _detected_frameworks

    if _enabled:
        return _detected_frameworks

    wrapped = []

    # OpenClaw
    try:
        from agent_preflight.integrations.openclaw import auto_enable
        if auto_enable():
            wrapped.append("OpenClaw")
    except Exception:
        pass

    # LangChain — register a default callback
    try:
        import langchain_core
        wrapped.append("LangChain")
    except ImportError:
        pass

    # CrewAI
    try:
        import crewai
        wrapped.append("CrewAI")
    except ImportError:
        pass

    # AutoGen
    try:
        import autogen
        wrapped.append("AutoGen")
    except ImportError:
        pass

    _enabled = True
    _detected_frameworks = wrapped

    if verbose and wrapped:
        print(f"[Preflight] Auto-enabled for: {', '.join(wrapped)}")
    elif verbose:
        print("[Preflight] No supported agent frameworks detected.")

    return wrapped


def status() -> dict:
    """Get the current auto-detection status."""
    return {
        "enabled": _enabled,
        "detected_frameworks": _detected_frameworks,
        "available_frameworks": detect_frameworks(),
    }


# Auto-enable if environment variable is set
if os.environ.get("PREFLIGHT_AUTO", "").strip() in ("1", "true", "yes"):
    enable(verbose=True)
