"""Tests for the policy engine."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_preflight import Preflight, RiskLevel, ActionType, Reversibility
from agent_preflight.policy import Policy, PolicyEngine, PolicyVerdict


def _make_plan(actions_fn, task="test"):
    pf = Preflight()

    @pf.intercept
    def send_email(to, body): pass
    @pf.intercept
    def get_data(query): pass
    @pf.intercept
    def delete_records(table): pass
    @pf.intercept
    def run_query(sql): pass
    @pf.intercept(cost=0.10)
    def expensive_op(): pass

    plan = pf.dry_run(lambda: actions_fn(
        send_email, get_data, delete_records, run_query, expensive_op
    ), task=task)
    return plan


def test_deny_by_risk_level():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        delete_records("users")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No high risk").when(risk_level=RiskLevel.HIGH))
    result = engine.evaluate(plan)
    assert result.blocked
    assert len(result.violations) >= 1
    assert result.violations[0].verdict == PolicyVerdict.DENY
    print("PASS: deny_by_risk_level")


def test_deny_by_args_match():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        run_query("DROP TABLE users")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No DROP").when_args_match(r"DROP TABLE"))
    result = engine.evaluate(plan)
    assert result.blocked
    print("PASS: deny_by_args_match")


def test_allow_clean_plan():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        get_data("SELECT * FROM users")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No drops").when_args_match(r"DROP TABLE"))
    result = engine.evaluate(plan)
    assert result.clean
    assert not result.blocked
    print("PASS: allow_clean_plan")


def test_budget_limit():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        expensive_op()
        expensive_op()
        expensive_op()

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.budget_limit("Budget cap", max_cost=0.20))
    result = engine.evaluate(plan)
    assert result.blocked
    assert any("cost" in v.details.lower() for v in result.violations)
    print("PASS: budget_limit")


def test_max_actions():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        for _ in range(5):
            get_data("x")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.max_actions("Too many", limit=3))
    result = engine.evaluate(plan)
    assert result.blocked
    print("PASS: max_actions")


def test_require_approval():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        send_email("boss@acme.com", "hello")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.require_approval("Review emails").when(
        action_type=ActionType.WRITE
    ))
    result = engine.evaluate(plan)
    assert result.needs_approval
    assert not result.blocked
    print("PASS: require_approval")


def test_warn_policy():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        get_data("users")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.warn("Monitor reads").when(action_type=ActionType.READ))
    result = engine.evaluate(plan)
    assert result.has_warnings
    assert not result.blocked
    print("PASS: warn_policy")


def test_custom_condition():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        send_email("external@gmail.com", "secrets")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(
        Policy.deny("No external emails")
        .when_custom(lambda a: a.name == "send_email" and "gmail" in str(a.args))
        .reason("External email addresses are blocked")
    )
    result = engine.evaluate(plan)
    assert result.blocked
    assert "External email" in result.violations[0].reason
    print("PASS: custom_condition")


def test_no_irreversible_policy():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        send_email("a@b.com", "hi")
        delete_records("data")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.no_irreversible())
    result = engine.evaluate(plan)
    assert result.blocked
    assert len(result.violations) >= 2  # both send_email and delete are irreversible
    print("PASS: no_irreversible_policy")


def test_policy_summary():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        delete_records("prod_data")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No deletes").when(action_type=ActionType.DELETE))
    result = engine.evaluate(plan)
    summary = result.summary()
    assert "BLOCKED" in summary
    assert "DENY" in summary
    print("PASS: policy_summary")


def test_policy_result_to_dict():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        get_data("safe")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No drops").when_args_match(r"DROP"))
    result = engine.evaluate(plan)
    d = result.to_dict()
    assert "blocked" in d
    assert d["blocked"] is False
    assert d["passed"] == 1
    print("PASS: policy_result_to_dict")


def test_multiple_policies():
    def actions(send_email, get_data, delete_records, run_query, expensive_op):
        send_email("a@b.com", "hi")
        delete_records("data")
        run_query("DROP TABLE logs")

    plan = _make_plan(actions)
    engine = PolicyEngine()
    engine.add(Policy.deny("No drops").when_args_match(r"DROP TABLE"))
    engine.add(Policy.deny("No deletes").when(action_type=ActionType.DELETE))
    engine.add(Policy.warn("Watch emails").when(name=r"send_email"))
    result = engine.evaluate(plan)
    assert result.blocked
    assert result.has_warnings
    assert len(result.violations) >= 3
    print("PASS: multiple_policies")


if __name__ == "__main__":
    test_deny_by_risk_level()
    test_deny_by_args_match()
    test_allow_clean_plan()
    test_budget_limit()
    test_max_actions()
    test_require_approval()
    test_warn_policy()
    test_custom_condition()
    test_no_irreversible_policy()
    test_policy_summary()
    test_policy_result_to_dict()
    test_multiple_policies()
    print()
    print("All 12 policy tests passed!")
