"""
OpenClaw Integration — embeds ATF governance into OpenClaw agents.

Wraps the OpenClaw tool executor to route all tool calls through
the ATF gateway. Designed for zero-config adoption:

    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()

Or via CLI:
    preflight enable --openclaw
"""

from __future__ import annotations

import asyncio
import functools
import json
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig, ExecutionMode
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent, Verdict
from agent_preflight.atf.plugins import ALL_PLUGINS


class OpenClawPreflight:
    """ATF wrapper for OpenClaw tool execution.

    Intercepts tool calls, runs them through the ATF pipeline,
    and only allows execution if the verdict is ALLOW or WARN.

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
    ):
        self._config = config or ATFConfig.for_mode(mode)
        self._gateway = ATFGateway(self._config)
        self._on_block = on_block
        self._on_warn = on_warn
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the ATF gateway and register plugins."""
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
    ) -> dict[str, Any]:
        """Intercept a single tool call through the ATF pipeline.

        Returns the pipeline result as a dict. If the action is blocked,
        includes correction feedback. If allowed, includes the passport.
        """
        if not self._initialized:
            await self.initialize()

        # Build structured intent from available info
        intent = StructuredIntent(
            goal=intent_goal or f"Execute {tool_name}",
            reasoning_summary=f"OpenClaw agent requesting {tool_name}",
            expected_state_changes=[],
            external_calls=[],
            irreversible=False,
            estimated_cost=0.0,
            confidence=0.7,
        )

        envelope = ActionEnvelope(
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            intent=intent,
        )

        result = await self._gateway.intercept_and_execute(envelope, tool_fn)

        # Fire callbacks
        if result.verdict == Verdict.BLOCK and self._on_block:
            self._on_block(result)
        elif result.verdict == Verdict.WARN and self._on_warn:
            self._on_warn(result)

        return result.to_agent_response()

    def wrap_executor(self, executor: Callable) -> Callable:
        """Wrap an OpenClaw tool executor with ATF governance.

        The wrapped executor will intercept every tool call, run it
        through the pipeline, and only call the original executor
        if the verdict allows it.
        """

        @functools.wraps(executor)
        async def wrapped(tool_name: str, arguments: dict, **kwargs):
            result = await self.intercept(
                tool_name=tool_name,
                arguments=arguments,
                agent_id=kwargs.get("agent_id", "openclaw-agent"),
                tool_fn=lambda **a: executor(tool_name, a, **kwargs),
            )

            if result.get("verdict") == "block":
                return {
                    "error": "Action blocked by Agent Preflight",
                    "correction": result.get("correction"),
                    "human_summary": result.get("human_summary"),
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
                    "error": "Action blocked by Agent Preflight",
                    "correction": result.get("correction"),
                    "human_summary": result.get("human_summary"),
                }

            return executor(tool_name, arguments, **kwargs)

        return wrapped


# ---------------------------------------------------------------------------
# Quick-enable function
# ---------------------------------------------------------------------------

_global_preflight: Optional[OpenClawPreflight] = None


def enable_preflight(
    mode: ExecutionMode = ExecutionMode.SAFE,
    config: Optional[ATFConfig] = None,
) -> OpenClawPreflight:
    """Enable ATF governance for OpenClaw with minimal setup.

    Usage:
        from agent_preflight.integrations.openclaw import enable_preflight
        pf = enable_preflight()
        # All subsequent OpenClaw tool calls are now governed
    """
    global _global_preflight
    _global_preflight = OpenClawPreflight(config=config, mode=mode)
    return _global_preflight


def get_preflight() -> Optional[OpenClawPreflight]:
    """Get the global OpenClaw preflight instance."""
    return _global_preflight
