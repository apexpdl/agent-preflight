"""Tests for ATF YAML Policy Engine v2."""

import pytest
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
from agent_preflight.atf.policy_v2 import YAMLPolicyEngine, PolicyRule


def _make_envelope(tool_name="test_tool", **kwargs):
    return ActionEnvelope(
        agent_id=kwargs.get("agent_id", "test-agent"),
        tool_name=tool_name,
        arguments=kwargs.get("arguments", {}),
        resource_targets=kwargs.get("targets", []),
        intent=StructuredIntent(
            goal=kwargs.get("goal", "Test"),
            reasoning_summary="Test",
            irreversible=kwargs.get("irreversible", False),
            estimated_cost=kwargs.get("cost", 0.0),
            confidence=kwargs.get("confidence", 0.8),
        ),
    )


class TestPolicyRule:
    def test_path_startswith(self):
        rule = PolicyRule("no_prod", 'path startswith "/prod"', "block")
        e = _make_envelope(targets=["/prod/database"])
        violation = rule.evaluate(e)
        assert violation is not None
        assert violation.rule_name == "no_prod"

    def test_tool_equals(self):
        rule = PolicyRule("no_db", 'tool == "db_query"', "block")
        e = _make_envelope("db_query")
        assert rule.evaluate(e) is not None

    def test_tool_no_match(self):
        rule = PolicyRule("no_db", 'tool == "db_query"', "block")
        e = _make_envelope("read_file")
        assert rule.evaluate(e) is None

    def test_cost_threshold(self):
        rule = PolicyRule("cost_limit", "estimated_cost > 500", "require_approval")
        e = _make_envelope(cost=1000)
        assert rule.evaluate(e) is not None

    def test_cost_under_threshold(self):
        rule = PolicyRule("cost_limit", "estimated_cost > 500", "block")
        e = _make_envelope(cost=100)
        assert rule.evaluate(e) is None

    def test_irreversible(self):
        rule = PolicyRule("no_irreversible", "irreversible == true", "block")
        e = _make_envelope(irreversible=True)
        assert rule.evaluate(e) is not None

    def test_and_condition(self):
        rule = PolicyRule(
            "complex", 'tool == "db_query" AND irreversible == true', "block"
        )
        e = _make_envelope("db_query", irreversible=True)
        assert rule.evaluate(e) is not None

    def test_and_partial_match(self):
        rule = PolicyRule(
            "complex", 'tool == "db_query" AND irreversible == true', "block"
        )
        e = _make_envelope("db_query", irreversible=False)
        assert rule.evaluate(e) is None

    def test_args_match(self):
        rule = PolicyRule("no_drop", 'args_match "DROP TABLE"', "block")
        e = _make_envelope(arguments={"query": "DROP TABLE users"})
        assert rule.evaluate(e) is not None


class TestYAMLPolicyEngine:
    def test_load_yaml(self):
        engine = YAMLPolicyEngine()
        yaml_content = """
rules:
  - name: "No prod deletion"
    condition: 'path startswith "/prod"'
    action: block
  - name: "Cost limit"
    condition: "estimated_cost > 500"
    action: require_approval
"""
        engine.load_yaml(yaml_content)
        e = _make_envelope(targets=["/prod/db"], cost=1000)
        decision = engine.evaluate(e)
        assert not decision.allow  # Blocked by prod rule
        assert decision.requires_approval  # Also needs approval for cost
        assert len(decision.violations) == 2

    def test_clean_evaluation(self):
        engine = YAMLPolicyEngine()
        engine.add_rule(PolicyRule("no_drop", 'args_match "DROP"', "block"))
        e = _make_envelope(arguments={"query": "SELECT * FROM users"})
        decision = engine.evaluate(e)
        assert decision.allow
        assert len(decision.violations) == 0

    def test_minimal_yaml_parser(self):
        engine = YAMLPolicyEngine()
        # Test the fallback parser (no PyYAML)
        yaml_like = """rules:
  - name: "Test rule"
    condition: 'tool == "danger"'
    action: block"""
        parsed = engine._minimal_parse(yaml_like)
        assert len(parsed["rules"]) == 1
        assert parsed["rules"][0]["name"] == "Test rule"
