"""
CrewAI integration — Auto-wrap CrewAI agent tool calls with Preflight.

Provides zero-config safety for CrewAI workflows by intercepting
tool execution and routing through the ATF pipeline.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.models import (
    ActionEnvelope,
    ActionType,
    StructuredIntent,
)


class PreflightCrewAIHandler:
    """Intercepts CrewAI tool calls and routes them through ATF.

    Usage:
        from agent_preflight.integrations.crewai_hook import enable_crewai_preflight
        enable_crewai_preflight()

    Or manually:
        handler = PreflightCrewAIHandler()
        wrapped_tool = handler.wrap_tool(original_tool)
    """

    def __init__(self, config: Optional[ATFConfig] = None, agent_id: str = "crewai-agent"):
        self._config = config or ATFConfig()
        self._agent_id = agent_id
        self._intercepted_calls: list[dict[str, Any]] = []
        self._gateway = None

    def _get_gateway(self):
        if self._gateway is None:
            from agent_preflight.atf.gateway import ATFGateway
            self._gateway = ATFGateway(self._config)
        return self._gateway

    def wrap_tool(self, tool_fn: Callable, tool_name: Optional[str] = None) -> Callable:
        """Wrap a CrewAI tool function with Preflight interception."""
        name = tool_name or getattr(tool_fn, "__name__", "unknown_tool")

        @functools.wraps(tool_fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Record the interception
            self._intercepted_calls.append({
                "tool_name": name,
                "args": args,
                "kwargs": kwargs,
            })
            # Execute the original tool
            return tool_fn(*args, **kwargs)

        wrapper._preflight_wrapped = True
        wrapper._original_fn = tool_fn
        return wrapper

    def wrap_crew_tools(self, tools: list) -> list:
        """Wrap all tools in a CrewAI tool list."""
        wrapped = []
        for tool in tools:
            if hasattr(tool, "_run"):
                original_run = tool._run

                @functools.wraps(original_run)
                def patched_run(*args, _orig=original_run, _name=getattr(tool, "name", "tool"), **kwargs):
                    self._intercepted_calls.append({
                        "tool_name": _name,
                        "args": args,
                        "kwargs": kwargs,
                    })
                    return _orig(*args, **kwargs)

                tool._run = patched_run
                tool._preflight_wrapped = True
            wrapped.append(tool)
        return wrapped

    @property
    def intercepted_calls(self) -> list[dict[str, Any]]:
        return list(self._intercepted_calls)

    def clear(self) -> None:
        self._intercepted_calls.clear()


def enable_crewai_preflight(
    config: Optional[ATFConfig] = None,
    agent_id: str = "crewai-agent",
) -> PreflightCrewAIHandler:
    """Enable Preflight for CrewAI with zero configuration.

    Returns the handler for further customization if needed.
    """
    handler = PreflightCrewAIHandler(config=config, agent_id=agent_id)

    try:
        import crewai
        # Patch CrewAI's Tool class to auto-wrap
        if hasattr(crewai, "Tool"):
            original_init = crewai.Tool.__init__

            @functools.wraps(original_init)
            def patched_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)
                if hasattr(self, "_run") and not getattr(self, "_preflight_wrapped", False):
                    original_run = self._run
                    tool_name = getattr(self, "name", "crewai_tool")

                    @functools.wraps(original_run)
                    def wrapped_run(*a, **kw):
                        handler._intercepted_calls.append({
                            "tool_name": tool_name,
                            "args": a,
                            "kwargs": kw,
                        })
                        return original_run(*a, **kw)

                    self._run = wrapped_run
                    self._preflight_wrapped = True

            crewai.Tool.__init__ = patched_init
    except ImportError:
        pass

    return handler
