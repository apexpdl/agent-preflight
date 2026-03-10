"""MCP middleware that intercepts tool calls through the Preflight pipeline.

Provides a drop-in middleware layer for MCP servers that transparently
routes every tool invocation through ATF governance before execution.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from agent_preflight.mcp.adapter import MCPPreflightAdapter
from agent_preflight.mcp.models import MCPPreflightResult, MCPToolCall


class PreflightMCPMiddleware:
    """Middleware that wraps an MCP server's tool dispatch.

    Usage::

        middleware = PreflightMCPMiddleware()
        await middleware.initialize()

        # Wrap every tool call
        result = await middleware.handle(tool_call, executor=original_handler)
    """

    def __init__(self, adapter: Optional[MCPPreflightAdapter] = None) -> None:
        self._adapter = adapter or MCPPreflightAdapter()

    async def initialize(self) -> None:
        """Initialize the underlying adapter."""
        await self._adapter.initialize()

    async def handle(
        self,
        tool_call: MCPToolCall,
        executor: Optional[Callable[..., Any]] = None,
    ) -> MCPPreflightResult:
        """Intercept a tool call through the governance pipeline.

        Parameters
        ----------
        tool_call:
            The MCP tool invocation to evaluate.
        executor:
            Optional callable to execute the tool if governance allows it.

        Returns
        -------
        MCPPreflightResult
            The governance decision and optional execution result.
        """
        return await self._adapter.intercept(tool_call, executor=executor)

    async def evaluate(self, tool_call: MCPToolCall) -> MCPPreflightResult:
        """Evaluate a tool call without executing it."""
        return await self._adapter.evaluate(tool_call)
