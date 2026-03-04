"""
Anthropic tool_use integration for agent-preflight.

Intercepts Anthropic API tool_use blocks from Claude responses and
feeds them into the preflight engine for analysis.

Example:
    from agent_preflight.integrations.anthropic_hook import PreflightAnthropic

    pf = Preflight()
    client = PreflightAnthropic(pf)

    response = anthropic_client.messages.create(...)
    client.capture_from_response(response)

    plan = client.build_plan(task="User request")
    print(pf.format(plan))
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ..core import Preflight
from ..models import Plan


class PreflightAnthropic:
    """
    Captures Anthropic Claude tool_use blocks for preflight analysis.

    Works with the Anthropic Python SDK response objects.
    """

    def __init__(
        self,
        preflight: Optional[Preflight] = None,
    ) -> None:
        self._pf = preflight or Preflight()
        self._tool_executors: dict[str, Callable] = {}

    def register_tool(self, name: str, executor: Callable) -> "PreflightAnthropic":
        """Register a function that executes a tool call."""
        self._tool_executors[name] = executor
        return self

    def capture_from_response(self, response: Any) -> list[str]:
        """
        Extract and capture tool_use blocks from an Anthropic Messages response.

        Handles both SDK response objects and raw dict responses.

        Args:
            response: An Anthropic Messages response (object or dict).

        Returns:
            List of captured tool names.
        """
        captured = []

        # Get content blocks
        if hasattr(response, "content"):
            content_blocks = response.content
        elif isinstance(response, dict):
            content_blocks = response.get("content", [])
        else:
            return captured

        for block in content_blocks:
            # Check if this is a tool_use block
            if hasattr(block, "type"):
                block_type = block.type
                if block_type != "tool_use":
                    continue
                tool_name = block.name
                tool_input = block.input if hasattr(block, "input") else {}
            elif isinstance(block, dict):
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
            else:
                continue

            # Ensure tool_input is a dict
            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except json.JSONDecodeError:
                    tool_input = {"raw": tool_input}

            executor = self._tool_executors.get(tool_name)
            self._pf.capture(
                name=tool_name,
                args=tool_input,
                executor=executor,
            )
            captured.append(tool_name)

        return captured

    def build_plan(self, task: str = "") -> Plan:
        """Build a preflight plan from captured tool_use blocks."""
        return self._pf.build_plan(task=task)

    def reset(self) -> None:
        """Clear captured actions for a new analysis."""
        self._pf._captures = []
        self._pf._sequence = 0


def capture_tool_use(
    preflight: Preflight,
    response: Any,
    executors: Optional[dict[str, Callable]] = None,
) -> list[str]:
    """
    Convenience function to capture tool_use from an Anthropic response.

    Args:
        preflight: Preflight instance to capture into.
        response: Anthropic Messages response.
        executors: Optional dict mapping tool names to executor functions.

    Returns:
        List of captured tool names.
    """
    hook = PreflightAnthropic(preflight)
    if executors:
        for name, fn in executors.items():
            hook.register_tool(name, fn)
    return hook.capture_from_response(response)
