"""
LLM-powered semantic risk analysis for agent-preflight.

Goes beyond heuristic pattern matching by using an LLM to reason about
the *meaning* of agent actions and their potential consequences.

Example:
    analyzer = SemanticAnalyzer(provider="openai", model="gpt-4")
    analysis = analyzer.analyze(plan)
    print(analysis.summary)
    print(analysis.concerns)
    print(analysis.recommended_risk)

    # Or bring your own LLM function:
    analyzer = SemanticAnalyzer(llm_fn=my_custom_llm)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .models import Plan, RiskLevel


@dataclass
class SemanticAnalysis:
    """Result of semantic analysis by an LLM."""
    summary: str = ""
    concerns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    recommended_risk: Optional[RiskLevel] = None
    action_notes: dict[str, str] = field(default_factory=dict)
    chain_analysis: str = ""
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "concerns": self.concerns,
            "recommendations": self.recommendations,
            "recommended_risk": self.recommended_risk.value if self.recommended_risk else None,
            "action_notes": self.action_notes,
            "chain_analysis": self.chain_analysis,
        }


_ANALYSIS_PROMPT = """You are an AI safety analyst. Analyze this agent execution plan and provide a risk assessment.

PLAN:
Task: {task}
Actions (in order):
{actions}

Respond in this exact JSON format:
{{
  "summary": "One paragraph overall assessment",
  "concerns": ["List of specific safety concerns"],
  "recommendations": ["List of recommendations to reduce risk"],
  "recommended_risk": "LOW|MEDIUM|HIGH|CRITICAL",
  "action_notes": {{"action_name": "specific note about this action"}},
  "chain_analysis": "Analysis of how these actions interact - does the sequence create emergent risks?"
}}

Focus on:
1. Could any action cause irreversible damage?
2. Is the sequence of actions logical and safe?
3. Are there missing safety checks (e.g., read before delete)?
4. Could the combination of actions create problems that individual actions wouldn't?
5. Are there potential data loss, financial, or privacy risks?
"""


def _format_actions(plan: Plan) -> str:
    lines = []
    for i, action in enumerate(plan.actions):
        all_args = {**action.args, **action.kwargs}
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in all_args.items())
        lines.append(
            f"  {i+1}. {action.name}({args_str})"
            f" [type={action.action_type.value},"
            f" risk={action.risk_level.value},"
            f" reversible={action.reversibility.value}]"
        )
        for reason in action.risk_reasons:
            lines.append(f"     Warning: {reason}")
    return "\n".join(lines)


def _parse_response(text: str) -> SemanticAnalysis:
    """Parse LLM JSON response into SemanticAnalysis."""
    analysis = SemanticAnalysis(raw_response=text)

    # Try to extract JSON from the response
    try:
        # Handle markdown code blocks
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]

        data = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        # If JSON parsing fails, use the raw text as summary
        analysis.summary = text
        return analysis

    analysis.summary = data.get("summary", "")
    analysis.concerns = data.get("concerns", [])
    analysis.recommendations = data.get("recommendations", [])
    analysis.action_notes = data.get("action_notes", {})
    analysis.chain_analysis = data.get("chain_analysis", "")

    risk_str = data.get("recommended_risk", "").upper()
    risk_map = {r.value: r for r in RiskLevel}
    analysis.recommended_risk = risk_map.get(risk_str)

    return analysis


class SemanticAnalyzer:
    """
    Uses an LLM to perform semantic risk analysis on agent plans.

    Supports three modes:
    1. OpenAI-compatible API (provider="openai")
    2. Anthropic API (provider="anthropic")
    3. Custom LLM function (llm_fn=your_function)

    The custom function should accept a string prompt and return a string response.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        llm_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._llm_fn = llm_fn

        if llm_fn is None and provider is None:
            raise ValueError(
                "Provide either provider ('openai'/'anthropic') or a custom llm_fn"
            )

    def _call_llm(self, prompt: str) -> str:
        """Route to the appropriate LLM backend."""
        if self._llm_fn:
            return self._llm_fn(prompt)

        if self._provider == "openai":
            return self._call_openai(prompt)
        elif self._provider == "anthropic":
            return self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unknown provider: {self._provider}")

    def _call_openai(self, prompt: str) -> str:
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model or "gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self._model or "claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def analyze(self, plan: Plan) -> SemanticAnalysis:
        """Analyze a plan using LLM-powered semantic reasoning."""
        actions_text = _format_actions(plan)
        prompt = _ANALYSIS_PROMPT.format(
            task=plan.task_description or "(no description)",
            actions=actions_text,
        )
        response = self._call_llm(prompt)
        return _parse_response(response)

    def analyze_with_context(
        self,
        plan: Plan,
        context: str,
    ) -> SemanticAnalysis:
        """Analyze with additional context about the system/environment."""
        actions_text = _format_actions(plan)
        prompt = _ANALYSIS_PROMPT.format(
            task=plan.task_description or "(no description)",
            actions=actions_text,
        )
        prompt += f"\n\nADDITIONAL CONTEXT:\n{context}"
        response = self._call_llm(prompt)
        return _parse_response(response)
