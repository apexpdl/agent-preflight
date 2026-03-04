"""
Self-Correcting Feedback Loop — generates structured correction messages
when Mirror World or policy evaluation blocks an action.

Returns actionable feedback that agents can use to revise their plans
without human intervention.
"""

from __future__ import annotations

from typing import Optional

from agent_preflight.atf.models import (
    ActionEnvelope,
    CorrectionFeedback,
    MirrorResult,
    PolicyDecision,
    RiskAssessment,
    SimulationResult,
)


class FeedbackGenerator:
    """Generates structured correction feedback for blocked actions."""

    def generate(
        self,
        envelope: ActionEnvelope,
        risk: RiskAssessment,
        policy: Optional[PolicyDecision] = None,
        mirror: Optional[MirrorResult] = None,
        simulation: Optional[SimulationResult] = None,
    ) -> CorrectionFeedback:
        """Generate correction feedback based on pipeline results."""
        violations: list[str] = []
        suggestions: list[str] = []
        rewrite_hints: list[str] = []
        actual_result_parts: list[str] = []

        # Risk-based feedback
        if risk.score >= 0.8:
            actual_result_parts.append(f"Risk score critically high: {risk.score:.2f}")
            for flag in risk.flags:
                violations.append(f"Risk flag: {flag}")

            if "irreversible" in risk.flags:
                suggestions.append("Mark action as reversible or add rollback mechanism")
                rewrite_hints.append("Add a backup/snapshot step before this action")

            if "destructive_tool" in risk.flags:
                suggestions.append("Use a safer alternative to destructive operations")
                rewrite_hints.append("Split into read-verify-then-delete pattern")

            if "sensitive_path" in risk.flags:
                suggestions.append("Target a less sensitive path or use staging environment")

            if "shell_execution" in risk.flags:
                suggestions.append("Use specific tool APIs instead of shell execution")

        # Policy-based feedback
        if policy and not policy.allow:
            for v in policy.violations:
                violations.append(f"Policy violation [{v.rule_name}]: {v.description}")
                actual_result_parts.append(f"Blocked by policy: {v.rule_name}")
            suggestions.append("Review policy constraints and adjust action parameters")
            rewrite_hints.append("Check time windows, cost limits, and path restrictions")

        # Mirror-based feedback
        if mirror and not mirror.matches_intent:
            for detail in mirror.mismatch_details:
                violations.append(f"Mirror mismatch: {detail}")
                actual_result_parts.append(detail)
            if mirror.external_attempts:
                suggestions.append(
                    f"Declare external calls in intent: {mirror.external_attempts}"
                )
                rewrite_hints.append("Add undeclared URLs to intent.external_calls")
            if mirror.permission_violations:
                suggestions.append("Request appropriate permissions for target resources")
            if mirror.exceptions:
                suggestions.append(
                    f"Handle potential exceptions: {[e.split(':')[0] for e in mirror.exceptions]}"
                )
                rewrite_hints.append("Add error handling for detected exception types")

        # Simulation-based feedback
        if simulation and simulation.failure_probability > 0.3:
            actual_result_parts.append(
                f"Simulation shows {simulation.failure_probability:.0%} failure probability"
            )
            if simulation.cascade_probability > 0.3:
                suggestions.append("Break action into smaller, isolated steps to reduce cascade risk")
                rewrite_hints.append("Decompose into atomic operations with checkpoints")
            if simulation.volatility_score > 0.5:
                suggestions.append("Add retry logic or idempotency guarantees")
            for dr in simulation.domain_results:
                if dr.failure_detected:
                    suggestions.append(
                        f"[{dr.plugin_name}] {dr.failure_description}"
                    )

        return CorrectionFeedback(
            declared_goal=envelope.intent.goal,
            actual_result=" | ".join(actual_result_parts) if actual_result_parts else "Action blocked",
            violations=violations,
            suggestions=suggestions,
            rewrite_hints=rewrite_hints,
            blocked=True,
        )

    def generate_human_summary(
        self,
        envelope: ActionEnvelope,
        risk: RiskAssessment,
        simulation: Optional[SimulationResult] = None,
    ) -> str:
        """Generate a CEO-friendly plain-English summary of the action."""
        parts: list[str] = []

        # Describe what the agent wants to do
        parts.append(f'Agent "{envelope.agent_id}" wants to: {envelope.intent.goal}')

        # Risk level in plain English
        if risk.score < 0.3:
            parts.append(f"This is a low-risk action (risk: {risk.score:.0%}).")
        elif risk.score < 0.6:
            parts.append(f"This action has moderate risk ({risk.score:.0%}).")
        elif risk.score < 0.8:
            parts.append(f"This is a HIGH-RISK action ({risk.score:.0%}).")
        else:
            parts.append(f"CRITICAL RISK: This action scores {risk.score:.0%} risk.")

        # Key concerns
        if risk.flags:
            readable_flags = [f.replace("_", " ") for f in risk.flags[:3]]
            parts.append(f"Key concerns: {', '.join(readable_flags)}.")

        # Simulation results
        if simulation and simulation.failure_probability > 0.1:
            parts.append(
                f"Simulation of {simulation.rollout_count} scenarios shows "
                f"{simulation.failure_probability:.0%} chance of failure."
            )
            if simulation.cascade_probability > 0.2:
                parts.append(
                    f"There is a {simulation.cascade_probability:.0%} chance of cascading effects."
                )

        # Cost
        if envelope.intent.estimated_cost > 0:
            parts.append(f"Estimated cost: ${envelope.intent.estimated_cost:.2f}.")

        # Irreversibility warning
        if envelope.intent.irreversible:
            parts.append("WARNING: This action cannot be undone.")

        return " ".join(parts)
