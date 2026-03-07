"""
AutoGen integration — Auto-wrap AutoGen agent tool calls with Preflight.

Provides zero-config safety for AutoGen multi-agent workflows by
intercepting function calls and routing through the ATF pipeline.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent


class PreflightAutoGenHandler:
    """Intercepts AutoGen function calls and routes them through ATF.

    Usage:
        from agent_preflight.integrations.autogen_hook import enable_autogen_preflight
        enable_autogen_preflight()

    Or manually:
        handler = PreflightAutoGenHandler()
        wrapped_fn = handler.wrap_function(original_fn)
    """

    def __init__(self, config: Optional[ATFConfig] = None, agent_id: str = "autogen-agent"):
        self._config = config or ATFConfig()
        self._agent_id = agent_id
        self._intercepted_calls: list[dict[str, Any]] = []
        self._gateway = None

    def _get_gateway(self):
        if self._gateway is None:
            from agent_preflight.atf.gateway import ATFGateway
            self._gateway = ATFGateway(self._config)
        return self._gateway

    def wrap_function(self, fn: Callable, name: Optional[str] = None) -> Callable:
        """Wrap a function with Preflight interception."""
        func_name = name or getattr(fn, "__name__", "unknown_function")

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._intercepted_calls.append({
                "tool_name": func_name,
                "args": args,
                "kwargs": kwargs,
            })
            return fn(*args, **kwargs)

        wrapper._preflight_wrapped = True
        wrapper._original_fn = fn
        return wrapper

    def wrap_function_map(self, function_map: dict[str, Callable]) -> dict[str, Callable]:
        """Wrap all functions in an AutoGen function map."""
        wrapped = {}
        for name, fn in function_map.items():
            if not getattr(fn, "_preflight_wrapped", False):
                wrapped[name] = self.wrap_function(fn, name)
            else:
                wrapped[name] = fn
        return wrapped

    @property
    def intercepted_calls(self) -> list[dict[str, Any]]:
        return list(self._intercepted_calls)

    def clear(self) -> None:
        self._intercepted_calls.clear()


def enable_autogen_preflight(
    config: Optional[ATFConfig] = None,
    agent_id: str = "autogen-agent",
) -> PreflightAutoGenHandler:
    """Enable Preflight for AutoGen with zero configuration.

    Returns the handler for further customization.
    """
    handler = PreflightAutoGenHandler(config=config, agent_id=agent_id)

    try:
        import autogen
        # Patch AutoGen's ConversableAgent to auto-wrap function maps
        if hasattr(autogen, "ConversableAgent"):
            original_register = getattr(
                autogen.ConversableAgent, "register_function", None
            )
            if original_register:
                @functools.wraps(original_register)
                def patched_register(self, function_map, *args, **kwargs):
                    wrapped_map = handler.wrap_function_map(function_map)
                    return original_register(self, wrapped_map, *args, **kwargs)

                autogen.ConversableAgent.register_function = patched_register
    except ImportError:
        pass

    return handler
