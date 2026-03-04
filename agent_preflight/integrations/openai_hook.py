"""
OpenAI function-calling integration for agent-preflight.

Intercepts OpenAI API function/tool calls and feeds them into
the preflight engine for analysis before execution.

Example:
    from agent_preflight.integrations.openai_hook import PreflightOpenAI

    pf = Preflight()
    client = PreflightOpenAI(pf, api_key="sk-...")

    # Use like normal OpenAI client - but in preflight mode,
    # function calls are captured instead of executed
    response = client.chat(messages=[...], tools=[...])
    plan = client.build_plan(task="User request")
    print(pf.format(plan))
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ..core import Preflight
from ..models import Plan


class PreflightOpenAI:
    """
    Wraps OpenAI chat completions to intercept function/tool calls.

    In preflight mode, tool calls from the LLM response are captured
    for analysis instead of being executed.
    """

    def __init__(
        self,
        preflight: Optional[Preflight] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
    ) -> None:
        self._pf = preflight or Preflight()
        self._api_key = api_key
        self._model = model
        self._tool_executors: dict[str, Callable] = {}

    def register_tool(self, name: str, executor: Callable) -> "PreflightOpenAI":
        """Register a function that executes a tool call."""
        self._tool_executors[name] = executor
        return self

    def capture_from_response(self, response: Any) -> list[str]:
        """
        Extract and capture tool calls from an OpenAI chat completion response.

        Args:
            response: An OpenAI ChatCompletion response object or dict.

        Returns:
            List of captured tool call names.
        """
        captured = []

        # Handle both object and dict responses
        if hasattr(response, "choices"):
            choices = response.choices
        elif isinstance(response, dict):
            choices = response.get("choices", [])
        else:
            return captured

        for choice in choices:
            message = choice.message if hasattr(choice, "message") else choice.get("message", {})
            tool_calls = (
                message.tool_calls
                if hasattr(message, "tool_calls") and message.tool_calls
                else message.get("tool_calls") if isinstance(message, dict) else None
            )

            if not tool_calls:
                continue

            for tc in tool_calls:
                if hasattr(tc, "function"):
                    fn_name = tc.function.name
                    fn_args_str = tc.function.arguments
                elif isinstance(tc, dict):
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args_str = fn.get("arguments", "{}")
                else:
                    continue

                try:
                    fn_args = json.loads(fn_args_str)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {"raw": fn_args_str}

                executor = self._tool_executors.get(fn_name)
                self._pf.capture(
                    name=fn_name,
                    args=fn_args,
                    executor=executor,
                )
                captured.append(fn_name)

        return captured

    def build_plan(self, task: str = "") -> Plan:
        """Build a preflight plan from captured tool calls."""
        return self._pf.build_plan(task=task)

    def reset(self) -> None:
        """Clear captured actions for a new analysis."""
        self._pf._captures = []
        self._pf._sequence = 0


def capture_tool_calls(
    preflight: Preflight,
    response: Any,
    executors: Optional[dict[str, Callable]] = None,
) -> list[str]:
    """
    Convenience function to capture tool calls from an OpenAI response.

    Args:
        preflight: Preflight instance to capture into.
        response: OpenAI chat completion response.
        executors: Optional dict mapping tool names to executor functions.

    Returns:
        List of captured tool call names.
    """
    hook = PreflightOpenAI(preflight)
    if executors:
        for name, fn in executors.items():
            hook.register_tool(name, fn)
    return hook.capture_from_response(response)
