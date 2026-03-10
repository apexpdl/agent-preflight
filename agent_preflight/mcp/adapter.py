"""MCP-to-ATF adapter.

Converts MCP tool calls into ATF ActionEnvelopes, runs them through
the Preflight governance pipeline, and translates results back into
the MCP format.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Optional

from agent_preflight.atf.config import ATFConfig
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.models import (
    ActionEnvelope,
    ActionType,
    PipelineResult,
    StructuredIntent,
    Verdict,
)
from agent_preflight.mcp.models import MCPPreflightResult, MCPToolCall, MCPToolResult


# ---------------------------------------------------------------------------
# Tool-name patterns used to infer ActionType
# ---------------------------------------------------------------------------

_ACTION_TYPE_PATTERNS: list[tuple[re.Pattern[str], ActionType]] = [
    # Destructive operations
    (re.compile(r"(delete|remove|drop|truncate|destroy|purge)", re.I), ActionType.DELETE),
    # Write / create / update operations
    (re.compile(r"(write|create|insert|update|set|put|save|upload|push|modify|edit|patch|add)", re.I), ActionType.WRITE),
    # Read / query operations
    (re.compile(r"(read|get|fetch|list|search|query|find|lookup|describe|show|view|download|pull)", re.I), ActionType.READ),
    # Network / HTTP operations
    (re.compile(r"(http|request|send|email|notify|post|webhook|call_api|invoke_api|curl|ping|dns)", re.I), ActionType.NETWORK),
    # Shell / command execution
    (re.compile(r"(exec|run|shell|bash|command|spawn|subprocess|terminal|sh_)", re.I), ActionType.SHELL),
    # Filesystem operations
    (re.compile(r"(file|directory|folder|path|mkdir|rmdir|rename|move|copy|chmod|chown|symlink|mount)", re.I), ActionType.FILESYSTEM),
    # API call patterns
    (re.compile(r"(api|rpc|grpc|graphql|rest)", re.I), ActionType.API_CALL),
]


class MCPPreflightAdapter:
    """Adapts MCP tool calls to the Preflight ATF pipeline.

    This is the core bridge between the Model Context Protocol and
    Preflight's governance infrastructure.  It can operate in two modes:

    * **intercept** -- evaluate the tool call *and* execute it if allowed.
    * **evaluate**  -- evaluate only, returning the verdict without
      executing the tool.

    Usage::

        adapter = MCPPreflightAdapter()
        await adapter.initialize()

        # Intercept a tool call (evaluate + execute)
        result = await adapter.intercept(tool_call, executor=my_tool_fn)

        # Or just evaluate without executing
        result = await adapter.evaluate(tool_call)
    """

    def __init__(
        self,
        config: Optional[ATFConfig] = None,
        gateway: Optional[ATFGateway] = None,
    ) -> None:
        if gateway is not None:
            self._gateway = gateway
            self._owns_gateway = False
        else:
            self._gateway = ATFGateway(config or ATFConfig())
            self._owns_gateway = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the underlying ATF gateway (idempotent)."""
        if self._owns_gateway and not self._gateway._initialized:
            await self._gateway.initialize()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def intercept(
        self,
        tool_call: MCPToolCall,
        executor: Optional[Callable[..., Any]] = None,
    ) -> MCPPreflightResult:
        """Evaluate a tool call and optionally execute it.

        Parameters
        ----------
        tool_call:
            The incoming MCP tool invocation.
        executor:
            An async or sync callable that performs the actual tool work.
            Signature: ``executor(**tool_call.arguments) -> Any``.
            If *None* the call is evaluated but never executed.

        Returns
        -------
        MCPPreflightResult
            Contains the verdict, risk metadata, and (if executed) the
            tool result.
        """
        await self.initialize()

        envelope = self._to_envelope(tool_call)
        pipeline_result = await self._gateway.intercept_and_execute(envelope)

        preflight_result = self._to_preflight_result(tool_call, pipeline_result)

        # Execute if allowed and an executor was provided
        if executor is not None and pipeline_result.verdict in (
            Verdict.ALLOW,
            Verdict.WARN,
        ):
            tool_result = await self._execute(tool_call, executor)
            preflight_result.tool_result = tool_result

        return preflight_result

    async def evaluate(self, tool_call: MCPToolCall) -> MCPPreflightResult:
        """Evaluate a tool call without executing it.

        Returns the governance verdict and risk information only.
        """
        return await self.intercept(tool_call, executor=None)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _to_envelope(self, tool_call: MCPToolCall) -> ActionEnvelope:
        """Convert an MCPToolCall into an ATF ActionEnvelope."""
        action_type = self._infer_action_type(tool_call.name, tool_call.arguments)
        intent = self._build_intent(tool_call)

        # Derive resource targets from arguments when possible
        resource_targets = self._extract_resource_targets(tool_call.arguments)

        return ActionEnvelope(
            agent_id=tool_call.metadata.get("agent_id", f"mcp:{tool_call.server_name or 'unknown'}"),
            tool_name=tool_call.name,
            action_type=action_type,
            arguments=tool_call.arguments,
            intent=intent,
            resource_targets=resource_targets,
            metadata={
                "mcp_request_id": tool_call.id,
                "mcp_server": tool_call.server_name,
                **tool_call.metadata,
            },
        )

    def _infer_action_type(self, tool_name: str, arguments: dict[str, Any]) -> ActionType:
        """Infer the ATF ActionType from the MCP tool name and arguments.

        Uses pattern matching against the tool name.  Falls back to
        ``ActionType.EXECUTE`` when no pattern matches.
        """
        for pattern, action_type in _ACTION_TYPE_PATTERNS:
            if pattern.search(tool_name):
                return action_type

        # Check arguments for hints
        arg_str = " ".join(str(v) for v in arguments.values())
        if any(kw in arg_str.lower() for kw in ("http://", "https://", "ftp://")):
            return ActionType.NETWORK

        return ActionType.EXECUTE

    def _build_intent(self, tool_call: MCPToolCall) -> StructuredIntent:
        """Build a StructuredIntent from tool call metadata.

        When the caller has not supplied explicit intent fields in the
        metadata, reasonable defaults are synthesised from the tool name
        and arguments.
        """
        meta = tool_call.metadata

        goal = meta.get("goal", f"Execute MCP tool '{tool_call.name}'")
        reasoning = meta.get(
            "reasoning_summary",
            f"MCP tool call from server '{tool_call.server_name or 'unknown'}'"
            f" with {len(tool_call.arguments)} argument(s)",
        )

        irreversible = meta.get("irreversible", self._looks_irreversible(tool_call.name))
        confidence = meta.get("confidence", 0.5)

        external_calls: list[str] = []
        if self._infer_action_type(tool_call.name, tool_call.arguments) == ActionType.NETWORK:
            external_calls = self._extract_urls(tool_call.arguments)

        return StructuredIntent(
            goal=goal,
            reasoning_summary=reasoning,
            irreversible=irreversible,
            confidence=confidence,
            external_calls=external_calls,
            expected_state_changes=meta.get("expected_state_changes", []),
            estimated_cost=meta.get("estimated_cost", 0.0),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_irreversible(tool_name: str) -> bool:
        """Heuristic: does the tool name suggest an irreversible action?"""
        return bool(re.search(r"(delete|remove|drop|destroy|purge|truncate)", tool_name, re.I))

    @staticmethod
    def _extract_resource_targets(arguments: dict[str, Any]) -> list[str]:
        """Pull likely resource targets from arguments."""
        targets: list[str] = []
        path_keys = ("path", "file", "filepath", "filename", "directory", "dir",
                      "target", "url", "uri", "resource", "bucket", "database", "db")
        for key, value in arguments.items():
            if key.lower() in path_keys and isinstance(value, str) and value:
                targets.append(value)
        return targets

    @staticmethod
    def _extract_urls(arguments: dict[str, Any]) -> list[str]:
        """Extract URLs from argument values."""
        urls: list[str] = []
        url_re = re.compile(r"https?://[^\s\"']+")
        for value in arguments.values():
            if isinstance(value, str):
                urls.extend(url_re.findall(value))
        return urls

    @staticmethod
    def _to_preflight_result(
        tool_call: MCPToolCall,
        pipeline: PipelineResult,
    ) -> MCPPreflightResult:
        """Map a PipelineResult to an MCPPreflightResult."""
        suggestions: list[str] = []
        blocked_reason: str | None = None
        if pipeline.correction:
            suggestions = pipeline.correction.suggestions
            blocked_reason = pipeline.correction.actual_result

        return MCPPreflightResult(
            tool_call=tool_call,
            verdict=pipeline.verdict.value,
            risk_score=pipeline.risk_assessment.score,
            risk_factors=pipeline.risk_assessment.flags,
            passport_id=pipeline.passport.passport_id if pipeline.passport else None,
            blocked_reason=blocked_reason,
            suggestions=suggestions,
            pipeline_time_ms=pipeline.total_pipeline_time_ms,
        )

    @staticmethod
    async def _execute(
        tool_call: MCPToolCall,
        executor: Callable[..., Any],
    ) -> MCPToolResult:
        """Run the executor and wrap the output as an MCPToolResult."""
        try:
            import asyncio

            if asyncio.iscoroutinefunction(executor):
                raw = await executor(**tool_call.arguments)
            else:
                raw = executor(**tool_call.arguments)

            # Normalise output into MCP content blocks
            if isinstance(raw, list):
                content = raw
            elif isinstance(raw, dict):
                content = [raw]
            elif isinstance(raw, str):
                content = [{"type": "text", "text": raw}]
            else:
                content = [{"type": "text", "text": str(raw)}]

            return MCPToolResult(id=tool_call.id, content=content, is_error=False)

        except Exception as exc:
            return MCPToolResult(
                id=tool_call.id,
                content=[{"type": "text", "text": f"Tool execution error: {exc}"}],
                is_error=True,
            )
