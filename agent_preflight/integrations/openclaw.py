"""
OpenClaw Integration — embeds ATF governance into OpenClaw agents.

Three ways to use:

    # 1. Zero-config auto-detect (EASIEST)
    import agent_preflight.integrations.openclaw  # That's it. Done.

    # 2. One-line enable
    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()

    # 3. Wrap a specific agent
    from agent_preflight.integrations.openclaw import OpenClawPreflight
    pf = OpenClawPreflight()
    safe_executor = pf.wrap_executor(original_executor)

Or via CLI:
    preflight enable --openclaw
"""

from __future__ import annotations

import asyncio
import functools
import json
import sys
import os
import importlib
import threading
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig, ExecutionMode
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent, Verdict
from agent_preflight.atf.plugins import ALL_PLUGINS


# ---------------------------------------------------------------------------
# Risk threshold for interruption — only bother the user when it matters
# ---------------------------------------------------------------------------

# Actions below this risk score execute silently (no popup, no interruption).
# Actions above this threshold trigger a warning/block.
SILENT_THRESHOLD = 0.3  # 30% risk = safe enough to pass silently
WARN_THRESHOLD = 0.5    # 50% risk = warn but still allow
BLOCK_THRESHOLD = 0.8   # 80% risk = block and show correction


class OpenClawPreflight:
    """ATF wrapper for OpenClaw tool execution.

    Intercepts tool calls, runs them through the ATF pipeline,
    and only surfaces warnings/blocks when risk is actually high.

    Low-risk actions pass through silently. No annoying popups.

    Usage:
        oc = OpenClawPreflight()
        await oc.initialize()

        # Wrap a tool executor
        safe_executor = oc.wrap_executor(original_executor)

        # Or intercept individual calls
        result = await oc.intercept(tool_name, arguments, agent_id="my-agent")
    """

    def __init__(
        self,
        config: Optional[ATFConfig] = None,
        mode: ExecutionMode = ExecutionMode.SAFE,
        on_block: Optional[Callable] = None,
        on_warn: Optional[Callable] = None,
        on_allow: Optional[Callable] = None,
        silent: bool = True,
        auto_allow_user_initiated: bool = True,
    ):
        """Initialize OpenClaw Preflight.

        Args:
            config: Custom ATF configuration. If None, uses mode defaults.
            mode: Execution mode (SAFE, BALANCED, AGGRESSIVE, ENTERPRISE).
            on_block: Callback when action is blocked.
            on_warn: Callback when action triggers a warning.
            on_allow: Callback when action is silently allowed.
            silent: If True, low-risk actions pass without any output.
            auto_allow_user_initiated: If True, actions directly prompted by
                the user are given higher trust (reduced interruptions).
        """
        self._config = config or ATFConfig.for_mode(mode)
        self._gateway = ATFGateway(self._config)
        self._on_block = on_block
        self._on_warn = on_warn
        self._on_allow = on_allow
        self._silent = silent
        self._auto_allow_user_initiated = auto_allow_user_initiated
        self._initialized = False
        self._stats = {"allowed": 0, "warned": 0, "blocked": 0, "total": 0}

    @property
    def stats(self) -> dict[str, int]:
        """Get preflight statistics."""
        return dict(self._stats)

    async def initialize(self) -> None:
        """Initialize the ATF gateway and register plugins."""
        if self._initialized:
            return
        await self._gateway.initialize()
        self._gateway.register_plugins([p() for p in ALL_PLUGINS])
        self._initialized = True

    async def intercept(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str = "openclaw-agent",
        intent_goal: str = "",
        tool_fn: Optional[Callable] = None,
        user_initiated: bool = False,
    ) -> dict[str, Any]:
        """Intercept a single tool call through the ATF pipeline.

        Returns the pipeline result as a dict. If the action is blocked,
        includes correction feedback. If allowed, includes the passport.

        Smart behavior:
        - Low-risk actions pass silently (no popup, no interruption).
        - Medium-risk actions warn but still allow execution.
        - High-risk actions block and provide correction suggestions.
        - User-initiated actions get higher trust scores.
        """
        if not self._initialized:
            await self.initialize()

        # Build structured intent from available info
        confidence = 0.85 if user_initiated else 0.7
        intent = StructuredIntent(
            goal=intent_goal or f"Execute {tool_name}",
            reasoning_summary=f"OpenClaw agent requesting {tool_name}",
            expected_state_changes=[],
            external_calls=[],
            irreversible=False,
            estimated_cost=0.0,
            confidence=confidence,
        )

        envelope = ActionEnvelope(
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            intent=intent,
        )

        result = await self._gateway.intercept_and_execute(envelope, tool_fn)

        # Update stats
        self._stats["total"] += 1

        # Smart interruption logic
        if result.verdict == Verdict.BLOCK:
            self._stats["blocked"] += 1
            if self._on_block:
                self._on_block(result)
        elif result.verdict == Verdict.WARN:
            self._stats["warned"] += 1
            if self._on_warn:
                self._on_warn(result)
        else:
            self._stats["allowed"] += 1
            if self._on_allow:
                self._on_allow(result)

        return result.to_agent_response()

    def wrap_executor(self, executor: Callable) -> Callable:
        """Wrap an OpenClaw tool executor with ATF governance.

        The wrapped executor intercepts every tool call, runs it
        through the pipeline, and only calls the original executor
        if the verdict allows it.

        Low-risk actions execute normally with zero overhead visible
        to the user. Only risky actions trigger warnings or blocks.
        """

        @functools.wraps(executor)
        async def wrapped(tool_name: str, arguments: dict, **kwargs):
            user_initiated = kwargs.pop("user_initiated", False)
            result = await self.intercept(
                tool_name=tool_name,
                arguments=arguments,
                agent_id=kwargs.get("agent_id", "openclaw-agent"),
                tool_fn=lambda **a: executor(tool_name, a, **kwargs),
                user_initiated=user_initiated,
            )

            if result.get("verdict") == "block":
                return {
                    "error": "Action blocked by Preflight",
                    "risk_score": result.get("risk_score"),
                    "flags": result.get("flags", []),
                    "correction": result.get("correction"),
                    "human_summary": result.get("human_summary"),
                    "suggestion": "Try a safer alternative. See correction for details.",
                }

            # Execute the original tool
            return executor(tool_name, arguments, **kwargs)

        return wrapped

    def wrap_sync_executor(self, executor: Callable) -> Callable:
        """Wrap a synchronous OpenClaw tool executor."""

        @functools.wraps(executor)
        def wrapped(tool_name: str, arguments: dict, **kwargs):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    self.intercept(
                        tool_name=tool_name,
                        arguments=arguments,
                        agent_id=kwargs.get("agent_id", "openclaw-agent"),
                    )
                )
            finally:
                loop.close()

            if result.get("verdict") == "block":
                return {
                    "error": "Action blocked by Preflight",
                    "risk_score": result.get("risk_score"),
                    "flags": result.get("flags", []),
                    "correction": result.get("correction"),
                    "human_summary": result.get("human_summary"),
                }

            return executor(tool_name, arguments, **kwargs)

        return wrapped

    def wrap_tool(self, tool_fn: Callable) -> Callable:
        """Wrap a single tool function (decorator-style).

        Usage:
            @pf.wrap_tool
            def send_email(to, subject, body):
                ...
        """

        @functools.wraps(tool_fn)
        async def async_wrapped(*args, **kwargs):
            result = await self.intercept(
                tool_name=tool_fn.__name__,
                arguments=kwargs if kwargs else {"args": args},
                tool_fn=tool_fn,
            )
            if result.get("verdict") == "block":
                return {
                    "error": f"Preflight blocked {tool_fn.__name__}",
                    "human_summary": result.get("human_summary"),
                    "correction": result.get("correction"),
                }
            return tool_fn(*args, **kwargs)

        @functools.wraps(tool_fn)
        def sync_wrapped(*args, **kwargs):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    self.intercept(
                        tool_name=tool_fn.__name__,
                        arguments=kwargs if kwargs else {"args": args},
                    )
                )
            finally:
                loop.close()
            if result.get("verdict") == "block":
                return {
                    "error": f"Preflight blocked {tool_fn.__name__}",
                    "human_summary": result.get("human_summary"),
                    "correction": result.get("correction"),
                }
            return tool_fn(*args, **kwargs)

        if asyncio.iscoroutinefunction(tool_fn):
            return async_wrapped
        return sync_wrapped


# ---------------------------------------------------------------------------
# Quick-enable function (the "1-line" integration)
# ---------------------------------------------------------------------------

_global_preflight: Optional[OpenClawPreflight] = None


def enable_preflight(
    mode: ExecutionMode = ExecutionMode.SAFE,
    config: Optional[ATFConfig] = None,
    silent: bool = True,
    auto_allow_user_initiated: bool = True,
    on_block: Optional[Callable] = None,
    on_warn: Optional[Callable] = None,
) -> OpenClawPreflight:
    """Enable ATF governance for OpenClaw with minimal setup.

    This is the recommended way to integrate Preflight with OpenClaw.
    One line, zero config, automatic safety.

    Usage:
        from agent_preflight.integrations.openclaw import enable_preflight
        pf = enable_preflight()  # That's it. Done.

    Options:
        mode: SAFE (strictest), BALANCED, AGGRESSIVE, ENTERPRISE
        silent: True = low-risk actions pass without output
        auto_allow_user_initiated: True = user-prompted actions get higher trust
        on_block: callback(result) when actions are blocked
        on_warn: callback(result) when actions trigger warnings
    """
    global _global_preflight
    _global_preflight = OpenClawPreflight(
        config=config,
        mode=mode,
        on_block=on_block,
        on_warn=on_warn,
        silent=silent,
        auto_allow_user_initiated=auto_allow_user_initiated,
    )
    return _global_preflight


def get_preflight() -> Optional[OpenClawPreflight]:
    """Get the global OpenClaw preflight instance."""
    return _global_preflight


# ---------------------------------------------------------------------------
# Auto-detect & monkey-patch OpenClaw (the "zero-config" integration)
# ---------------------------------------------------------------------------

def _try_auto_patch() -> bool:
    """Attempt to auto-detect and patch OpenClaw if it's installed.

    This enables zero-config adoption: just `import agent_preflight`
    and if OpenClaw is present, all tool executions are automatically
    governed by Preflight.

    Returns True if OpenClaw was found and patched.
    """
    try:
        openclaw = importlib.import_module("openclaw")
    except ImportError:
        return False

    pf = enable_preflight(silent=True)

    # Patch the Agent class if it exists
    if hasattr(openclaw, "Agent"):
        _original_init = openclaw.Agent.__init__

        @functools.wraps(_original_init)
        def _patched_init(self, *args, **kwargs):
            _original_init(self, *args, **kwargs)
            # Wrap the tool executor if present
            if hasattr(self, "execute_tool"):
                self.execute_tool = pf.wrap_sync_executor(self.execute_tool)
            if hasattr(self, "async_execute_tool"):
                self.async_execute_tool = pf.wrap_executor(self.async_execute_tool)
            if hasattr(self, "_execute"):
                self._execute = pf.wrap_sync_executor(self._execute)
            if hasattr(self, "_async_execute"):
                self._async_execute = pf.wrap_executor(self._async_execute)

        openclaw.Agent.__init__ = _patched_init

    # Patch the tool executor if it's a module-level function
    if hasattr(openclaw, "execute_tool"):
        openclaw.execute_tool = pf.wrap_sync_executor(openclaw.execute_tool)

    if hasattr(openclaw, "run_tool"):
        openclaw.run_tool = pf.wrap_sync_executor(openclaw.run_tool)

    return True


# ---------------------------------------------------------------------------
# Auto-patch on import (opt-in via environment variable or explicit import)
# ---------------------------------------------------------------------------

_auto_patched = False


def auto_enable():
    """Explicitly trigger auto-detection and patching of OpenClaw.

    Call this if you want zero-config integration:

        import agent_preflight.integrations.openclaw as preflight
        preflight.auto_enable()

    Or set PREFLIGHT_AUTO=1 environment variable and it happens
    automatically when this module is imported.
    """
    global _auto_patched
    if not _auto_patched:
        _auto_patched = _try_auto_patch()
    return _auto_patched


# Auto-patch if environment variable is set
if os.environ.get("PREFLIGHT_AUTO", "").strip() in ("1", "true", "yes"):
    auto_enable()
