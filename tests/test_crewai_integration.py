"""Tests for CrewAI integration."""

import pytest
from agent_preflight.integrations.crewai_hook import PreflightCrewAIHandler


class TestCrewAIHandler:
    def setup_method(self):
        self.handler = PreflightCrewAIHandler()

    def test_wrap_tool(self):
        def my_tool(query):
            return f"result: {query}"

        wrapped = self.handler.wrap_tool(my_tool, "search_tool")
        result = wrapped("test query")

        assert result == "result: test query"
        assert len(self.handler.intercepted_calls) == 1
        assert self.handler.intercepted_calls[0]["tool_name"] == "search_tool"

    def test_wrap_preserves_function(self):
        def original(x, y):
            return x + y

        wrapped = self.handler.wrap_tool(original)
        assert wrapped(2, 3) == 5
        assert wrapped._preflight_wrapped is True

    def test_multiple_calls_tracked(self):
        def tool(x):
            return x

        wrapped = self.handler.wrap_tool(tool, "t1")
        wrapped(1)
        wrapped(2)
        wrapped(3)

        assert len(self.handler.intercepted_calls) == 3

    def test_clear(self):
        def tool():
            pass

        wrapped = self.handler.wrap_tool(tool)
        wrapped()
        self.handler.clear()
        assert len(self.handler.intercepted_calls) == 0

    def test_wrap_crew_tools(self):
        class FakeTool:
            name = "fake_tool"

            def _run(self, query):
                return f"ran: {query}"

        tools = [FakeTool()]
        wrapped = self.handler.wrap_crew_tools(tools)

        result = wrapped[0]._run("test")
        assert result == "ran: test"
        assert len(self.handler.intercepted_calls) == 1
