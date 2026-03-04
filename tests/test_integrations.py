"""Tests for framework integrations (OpenAI, Anthropic - using mock responses)."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_preflight import Preflight
from agent_preflight.integrations.openai_hook import PreflightOpenAI, capture_tool_calls
from agent_preflight.integrations.anthropic_hook import PreflightAnthropic, capture_tool_use


# Mock OpenAI response objects
class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

class MockToolCall:
    def __init__(self, name, arguments):
        self.function = MockFunction(name, arguments)

class MockMessage:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls

class MockChoice:
    def __init__(self, message):
        self.message = message

class MockOpenAIResponse:
    def __init__(self, tool_calls):
        self.choices = [MockChoice(MockMessage(tool_calls))]


# Mock Anthropic response objects
class MockToolUseBlock:
    def __init__(self, name, input_data):
        self.type = "tool_use"
        self.name = name
        self.input = input_data

class MockTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text

class MockAnthropicResponse:
    def __init__(self, content):
        self.content = content


def test_openai_capture():
    pf = Preflight()
    hook = PreflightOpenAI(pf)

    response = MockOpenAIResponse([
        MockToolCall("search_web", '{"query": "weather today"}'),
        MockToolCall("send_email", '{"to": "user@test.com", "body": "hi"}'),
    ])

    captured = hook.capture_from_response(response)
    assert len(captured) == 2
    assert "search_web" in captured
    assert "send_email" in captured

    plan = hook.build_plan(task="OpenAI test")
    assert len(plan.actions) == 2
    assert plan.actions[0].name == "search_web"
    assert plan.actions[0].args["query"] == "weather today"
    assert plan.actions[1].name == "send_email"
    print("PASS: openai_capture")


def test_openai_with_executor():
    pf = Preflight()
    hook = PreflightOpenAI(pf)
    executed = []
    hook.register_tool("greet", lambda name: executed.append(name))

    response = MockOpenAIResponse([
        MockToolCall("greet", '{"name": "Alice"}'),
    ])
    hook.capture_from_response(response)
    plan = hook.build_plan()

    plan.approve()
    plan.execute()
    assert executed == ["Alice"]
    print("PASS: openai_with_executor")


def test_openai_dict_response():
    pf = Preflight()
    hook = PreflightOpenAI(pf)

    response = {
        "choices": [{
            "message": {
                "tool_calls": [{
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "NYC"}',
                    }
                }]
            }
        }]
    }

    captured = hook.capture_from_response(response)
    assert captured == ["get_weather"]
    print("PASS: openai_dict_response")


def test_openai_convenience_fn():
    pf = Preflight()
    response = MockOpenAIResponse([
        MockToolCall("do_thing", '{"x": 1}'),
    ])
    captured = capture_tool_calls(pf, response)
    assert captured == ["do_thing"]
    print("PASS: openai_convenience_fn")


def test_openai_reset():
    pf = Preflight()
    hook = PreflightOpenAI(pf)

    response = MockOpenAIResponse([MockToolCall("a", '{}'), MockToolCall("b", '{}')])
    hook.capture_from_response(response)
    assert len(hook.build_plan().actions) == 2

    hook.reset()
    assert len(hook.build_plan().actions) == 0
    print("PASS: openai_reset")


def test_anthropic_capture():
    pf = Preflight()
    hook = PreflightAnthropic(pf)

    response = MockAnthropicResponse([
        MockTextBlock("I'll help you with that."),
        MockToolUseBlock("search_database", {"query": "active users"}),
        MockToolUseBlock("send_notification", {"user_id": 123, "message": "hello"}),
    ])

    captured = hook.capture_from_response(response)
    assert len(captured) == 2
    assert "search_database" in captured
    assert "send_notification" in captured

    plan = hook.build_plan(task="Anthropic test")
    assert len(plan.actions) == 2
    assert plan.actions[0].args["query"] == "active users"
    print("PASS: anthropic_capture")


def test_anthropic_dict_response():
    pf = Preflight()
    hook = PreflightAnthropic(pf)

    response = {
        "content": [
            {"type": "text", "text": "Here's what I'll do:"},
            {"type": "tool_use", "name": "calculate", "input": {"expr": "2+2"}},
        ]
    }

    captured = hook.capture_from_response(response)
    assert captured == ["calculate"]
    plan = hook.build_plan()
    assert plan.actions[0].args["expr"] == "2+2"
    print("PASS: anthropic_dict_response")


def test_anthropic_convenience_fn():
    pf = Preflight()
    response = MockAnthropicResponse([
        MockToolUseBlock("run_code", {"code": "print('hi')"}),
    ])
    captured = capture_tool_use(pf, response)
    assert captured == ["run_code"]
    print("PASS: anthropic_convenience_fn")


def test_anthropic_with_executor():
    pf = Preflight()
    hook = PreflightAnthropic(pf)
    results = []
    hook.register_tool("add", lambda a, b: results.append(a + b))

    response = MockAnthropicResponse([
        MockToolUseBlock("add", {"a": 3, "b": 4}),
    ])
    hook.capture_from_response(response)
    plan = hook.build_plan()
    plan.approve()
    plan.execute()
    assert results == [7]
    print("PASS: anthropic_with_executor")


def test_risk_classification_through_integrations():
    """Verify that actions captured through integrations get classified."""
    pf = Preflight()
    hook = PreflightOpenAI(pf)

    response = MockOpenAIResponse([
        MockToolCall("delete_all_users", '{}'),
        MockToolCall("send_email", '{"to": "a@b.com"}'),
        MockToolCall("get_data", '{"q": "test"}'),
    ])
    hook.capture_from_response(response)
    plan = hook.build_plan(task="integration risk test")

    # delete should be HIGH+
    delete_action = next(a for a in plan.actions if a.name == "delete_all_users")
    assert delete_action.risk_level.value in ("HIGH", "CRITICAL")

    # get_data should be LOW
    read_action = next(a for a in plan.actions if a.name == "get_data")
    assert read_action.risk_level.value == "LOW"
    print("PASS: risk_classification_through_integrations")


if __name__ == "__main__":
    test_openai_capture()
    test_openai_with_executor()
    test_openai_dict_response()
    test_openai_convenience_fn()
    test_openai_reset()
    test_anthropic_capture()
    test_anthropic_dict_response()
    test_anthropic_convenience_fn()
    test_anthropic_with_executor()
    test_risk_classification_through_integrations()
    print()
    print("All 10 integration tests passed!")
