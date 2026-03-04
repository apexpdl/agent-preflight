"""
LangChain/LangGraph integration for agent-preflight.

Provides a callback handler that intercepts LangChain tool calls
and feeds them into the preflight engine for analysis.

Example:
    from agent_preflight.integrations.langchain import PreflightCallbackHandler

    pf = Preflight()
    handler = PreflightCallbackHandler(pf)

    # Use with any LangChain agent
    agent.invoke({"input": "..."}, config={"callbacks": [handler]})

    plan = handler.build_plan(task="Agent task description")
    print(pf.format(plan))
"""

from __future__ import annotations

from typing import Any, Optional, Union

from ..core import Preflight
from ..models import Plan


def _safe_import_langchain():
    """Import LangChain callback base, raising a clear error if not installed."""
    try:
        from langchain_core.callbacks import BaseCallbackHandler
        return BaseCallbackHandler
    except ImportError:
        raise ImportError(
            "LangChain integration requires langchain-core. "
            "Install it with: pip install agent-preflight[langchain]"
        )


class PreflightCallbackHandler:
    """
    LangChain callback handler that captures tool calls for preflight analysis.

    Intercepts on_tool_start/on_tool_end events and feeds them to
    the Preflight engine for risk classification and plan building.
    """

    def __init__(self, preflight: Optional[Preflight] = None) -> None:
        BaseCallbackHandler = _safe_import_langchain()
        self._pf = preflight or Preflight()
        self._tool_outputs: dict[str, Any] = {}

        # Dynamically create a class that extends BaseCallbackHandler
        # This avoids import errors when langchain is not installed
        outer = self

        class _Handler(BaseCallbackHandler):
            """Internal LangChain callback handler."""

            @property
            def always_verbose(self) -> bool:
                return True

            def on_tool_start(
                self,
                serialized: dict[str, Any],
                input_str: str,
                *,
                run_id: Any = None,
                parent_run_id: Any = None,
                tags: Optional[list[str]] = None,
                metadata: Optional[dict[str, Any]] = None,
                **kwargs: Any,
            ) -> None:
                tool_name = serialized.get("name", "unknown_tool")

                # Parse input - could be string or dict
                if isinstance(input_str, str):
                    args = {"input": input_str}
                elif isinstance(input_str, dict):
                    args = input_str
                else:
                    args = {"input": str(input_str)}

                outer._pf.capture(name=tool_name, args=args)

            def on_tool_end(
                self,
                output: str,
                *,
                run_id: Any = None,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                # Store output for reference but don't affect the plan
                pass

            def on_tool_error(
                self,
                error: Union[Exception, KeyboardInterrupt],
                *,
                run_id: Any = None,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                pass

            # Required stubs for other callback events
            def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
                pass

            def on_llm_end(self, *args: Any, **kwargs: Any) -> None:
                pass

            def on_llm_error(self, *args: Any, **kwargs: Any) -> None:
                pass

            def on_chain_start(self, *args: Any, **kwargs: Any) -> None:
                pass

            def on_chain_end(self, *args: Any, **kwargs: Any) -> None:
                pass

            def on_chain_error(self, *args: Any, **kwargs: Any) -> None:
                pass

        self._handler = _Handler()

    @property
    def handler(self):
        """Get the LangChain-compatible callback handler instance."""
        return self._handler

    def build_plan(self, task: str = "") -> Plan:
        """Build a preflight plan from all captured tool calls."""
        return self._pf.build_plan(task=task)

    def reset(self) -> None:
        """Clear captured actions for a new run."""
        self._pf._captures = []
        self._pf._sequence = 0


class PreflightToolWrapper:
    """
    Wraps LangChain tools with preflight interception.

    Example:
        from langchain.tools import Tool
        wrapper = PreflightToolWrapper(pf)
        wrapped_tools = wrapper.wrap_tools([search_tool, email_tool])
    """

    def __init__(self, preflight: Preflight) -> None:
        self._pf = preflight

    def wrap_tool(self, tool: Any) -> Any:
        """Wrap a single LangChain tool with preflight capture."""
        try:
            from langchain_core.tools import BaseTool
        except ImportError:
            raise ImportError(
                "LangChain integration requires langchain-core. "
                "Install it with: pip install agent-preflight[langchain]"
            )

        original_run = tool._run
        pf = self._pf

        def intercepted_run(*args: Any, **kwargs: Any) -> Any:
            if pf._dry_run_mode:
                pf.capture(
                    name=tool.name,
                    args={"input": args[0] if args else ""},
                    kwargs=kwargs,
                )
                return f"[PREFLIGHT] {tool.name} captured"
            return original_run(*args, **kwargs)

        tool._run = intercepted_run
        return tool

    def wrap_tools(self, tools: list[Any]) -> list[Any]:
        """Wrap a list of LangChain tools."""
        return [self.wrap_tool(t) for t in tools]
