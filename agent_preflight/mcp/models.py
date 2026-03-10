"""Pydantic models for MCP (Model Context Protocol) integration.

These models represent the data flowing through the MCP-Preflight
interception layer: incoming tool calls, execution results, and
Preflight governance decisions.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MCPToolCall(BaseModel):
    """Represents an incoming MCP tool invocation.

    Captures everything needed to evaluate and optionally execute
    a tool call that arrived via the Model Context Protocol.
    """

    id: str = Field(..., min_length=1, description="MCP request ID")
    name: str = Field(..., min_length=1, description="Tool name")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )
    server_name: str = Field(
        default="", description="MCP server that provides this tool"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (session ID, caller info, etc.)",
    )

    @field_validator("name")
    @classmethod
    def normalize_tool_name(cls, v: str) -> str:
        """Strip whitespace from tool names."""
        return v.strip()


class MCPToolResult(BaseModel):
    """Result from executing an MCP tool.

    Follows the MCP content-block convention where results are
    returned as a list of typed content blocks.
    """

    id: str = Field(..., min_length=1, description="Matches the originating request ID")
    content: list[dict[str, Any]] = Field(
        default_factory=list, description="MCP content blocks"
    )
    is_error: bool = Field(
        default=False, description="Whether the tool execution failed"
    )


class MCPPreflightResult(BaseModel):
    """Preflight's decision on an MCP tool call.

    Combines the governance verdict with the optional execution
    result, providing a single object that callers can inspect.
    """

    tool_call: MCPToolCall
    verdict: str = Field(
        ..., description="Governance verdict: allow, warn, or block"
    )
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_factors: list[str] = Field(default_factory=list)
    passport_id: Optional[str] = None
    tool_result: Optional[MCPToolResult] = None
    blocked_reason: Optional[str] = None
    suggestions: list[str] = Field(default_factory=list)
    pipeline_time_ms: float = Field(default=0.0, ge=0.0)

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        allowed = {"allow", "warn", "block", "require_approval"}
        if v not in allowed:
            raise ValueError(f"verdict must be one of {allowed}, got {v!r}")
        return v
