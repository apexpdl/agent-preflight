"""Tests for semantic analysis (with mock LLM)."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_preflight import Preflight
from agent_preflight.semantic import SemanticAnalyzer, SemanticAnalysis, _parse_response


def _make_plan():
    pf = Preflight()
    @pf.intercept
    def send_email(to, body): pass
    @pf.intercept
    def delete_records(table): pass
    plan = pf.dry_run(lambda: (send_email("a@b.com", "hi"), delete_records("users")),
                       task="cleanup and notify")
    return plan


def test_parse_valid_json():
    response = json.dumps({
        "summary": "Plan looks risky",
        "concerns": ["Deleting users without backup"],
        "recommendations": ["Add backup step"],
        "recommended_risk": "HIGH",
        "action_notes": {"delete_records": "No safety check"},
        "chain_analysis": "Email sent before delete - OK",
    })
    analysis = _parse_response(response)
    assert analysis.summary == "Plan looks risky"
    assert len(analysis.concerns) == 1
    assert analysis.recommended_risk is not None
    assert analysis.recommended_risk.value == "HIGH"
    print("PASS: parse_valid_json")


def test_parse_json_in_markdown():
    response = '```json\n{"summary": "Test", "concerns": [], "recommendations": [], "recommended_risk": "LOW", "action_notes": {}, "chain_analysis": ""}\n```'
    analysis = _parse_response(response)
    assert analysis.summary == "Test"
    assert analysis.recommended_risk.value == "LOW"
    print("PASS: parse_json_in_markdown")


def test_parse_invalid_json():
    response = "This is just plain text analysis."
    analysis = _parse_response(response)
    assert analysis.summary == response
    assert analysis.raw_response == response
    print("PASS: parse_invalid_json")


def test_custom_llm_fn():
    def mock_llm(prompt):
        return json.dumps({
            "summary": "Mock analysis complete",
            "concerns": ["Test concern"],
            "recommendations": ["Test recommendation"],
            "recommended_risk": "MEDIUM",
            "action_notes": {},
            "chain_analysis": "Looks fine",
        })

    analyzer = SemanticAnalyzer(llm_fn=mock_llm)
    plan = _make_plan()
    analysis = analyzer.analyze(plan)
    assert analysis.summary == "Mock analysis complete"
    assert len(analysis.concerns) == 1
    assert analysis.recommended_risk.value == "MEDIUM"
    print("PASS: custom_llm_fn")


def test_analyze_with_context():
    def mock_llm(prompt):
        assert "production database" in prompt
        return json.dumps({
            "summary": "High risk - production system",
            "concerns": ["Production data at risk"],
            "recommendations": ["Use staging first"],
            "recommended_risk": "CRITICAL",
            "action_notes": {},
            "chain_analysis": "",
        })

    analyzer = SemanticAnalyzer(llm_fn=mock_llm)
    plan = _make_plan()
    analysis = analyzer.analyze_with_context(plan, context="This runs against a production database")
    assert analysis.recommended_risk.value == "CRITICAL"
    print("PASS: analyze_with_context")


def test_analysis_to_dict():
    analysis = SemanticAnalysis(
        summary="Test",
        concerns=["A", "B"],
        recommendations=["X"],
        action_notes={"foo": "bar"},
    )
    d = analysis.to_dict()
    assert d["summary"] == "Test"
    assert len(d["concerns"]) == 2
    assert d["recommended_risk"] is None
    print("PASS: analysis_to_dict")


def test_no_provider_error():
    try:
        SemanticAnalyzer()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "provider" in str(e).lower() or "llm_fn" in str(e).lower()
    print("PASS: no_provider_error")


if __name__ == "__main__":
    test_parse_valid_json()
    test_parse_json_in_markdown()
    test_parse_invalid_json()
    test_custom_llm_fn()
    test_analyze_with_context()
    test_analysis_to_dict()
    test_no_provider_error()
    print()
    print("All 7 semantic tests passed!")
