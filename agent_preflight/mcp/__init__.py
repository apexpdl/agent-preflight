"""MCP (Model Context Protocol) integration for Preflight.

Provides middleware that intercepts MCP tool calls and routes them
through the Preflight governance pipeline before execution.
"""

from agent_preflight.mcp.adapter import MCPPreflightAdapter
from agent_preflight.mcp.middleware import PreflightMCPMiddleware
from agent_preflight.mcp.models import MCPToolCall, MCPToolResult, MCPPreflightResult

__all__ = [
    "MCPPreflightAdapter",
    "PreflightMCPMiddleware",
    "MCPToolCall",
    "MCPToolResult",
    "MCPPreflightResult",
]
