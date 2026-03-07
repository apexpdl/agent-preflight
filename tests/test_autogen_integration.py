"""Tests for AutoGen integration."""

import pytest
from agent_preflight.integrations.autogen_hook import PreflightAutoGenHandler


class TestAutoGenHandler:
    def setup_method(self):
        self.handler = PreflightAutoGenHandler()

    def test_wrap_function(self):
        def my_func(x):
            return x * 2

        wrapped = self.handler.wrap_function(my_func, "double")
        result = wrapped(5)

        assert result == 10
        assert len(self.handler.intercepted_calls) == 1
        assert self.handler.intercepted_calls[0]["tool_name"] == "double"

    def test_wrap_function_map(self):
        def add(a, b):
            return a + b

        def multiply(a, b):
            return a * b

        func_map = {"add": add, "multiply": multiply}
        wrapped_map = self.handler.wrap_function_map(func_map)

        assert wrapped_map["add"](2, 3) == 5
        assert wrapped_map["multiply"](4, 5) == 20
        assert len(self.handler.intercepted_calls) == 2

    def test_already_wrapped_skipped(self):
        def my_func():
            pass

        wrapped = self.handler.wrap_function(my_func, "f1")
        func_map = {"f1": wrapped}
        result_map = self.handler.wrap_function_map(func_map)

        # Should not double-wrap
        assert result_map["f1"]._preflight_wrapped is True

    def test_clear(self):
        def f():
            pass

        wrapped = self.handler.wrap_function(f)
        wrapped()
        self.handler.clear()
        assert len(self.handler.intercepted_calls) == 0
