"""
Policy Engine v2 — YAML-based compliance-as-code.

Reads declarative policy rules from YAML files and evaluates them
against action envelopes in real-time. Supports time-based conditions,
cost thresholds, path restrictions, and tool-specific controls.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent_preflight.atf.models import ActionEnvelope, PolicyDecision, PolicyViolation

# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------


def _eval_condition(condition: str, envelope: ActionEnvelope) -> bool:
    """Evaluate a policy condition string against an action envelope.

    Supported conditions:
    - path startswith "/prod"
    - tool == "db_query"
    - estimated_cost > 500
    - irreversible == true
    - time outside 9-18
    - agent_id == "..."
    - args_match "pattern"
    - AND / OR combinators
    """
    condition = condition.strip()

    # Handle AND/OR
    if " AND " in condition:
        parts = condition.split(" AND ")
        return all(_eval_condition(p, envelope) for p in parts)
    if " OR " in condition:
        parts = condition.split(" OR ")
        return any(_eval_condition(p, envelope) for p in parts)

    # path startswith
    m = re.match(r'path\s+startswith\s+"([^"]+)"', condition)
    if m:
        prefix = m.group(1)
        targets = envelope.resource_targets + [str(v) for v in envelope.arguments.values() if isinstance(v, str)]
        return any(t.startswith(prefix) for t in targets)

    # tool ==
    m = re.match(r'tool\s*==\s*"([^"]+)"', condition)
    if m:
        return envelope.tool_name == m.group(1)

    # tool matches
    m = re.match(r'tool\s+matches\s+"([^"]+)"', condition)
    if m:
        return bool(re.search(m.group(1), envelope.tool_name, re.IGNORECASE))

    # estimated_cost >
    m = re.match(r"estimated_cost\s*>\s*(\d+\.?\d*)", condition)
    if m:
        return envelope.intent.estimated_cost > float(m.group(1))

    # irreversible == true
    if condition.strip().lower() in ("irreversible == true", "irreversible"):
        return envelope.intent.irreversible

    # time outside H-H
    m = re.match(r"time\s+outside\s+(\d+)-(\d+)", condition)
    if m:
        start_h, end_h = int(m.group(1)), int(m.group(2))
        current_h = datetime.now(timezone.utc).hour
        return current_h < start_h or current_h >= end_h

    # agent_id ==
    m = re.match(r'agent_id\s*==\s*"([^"]+)"', condition)
    if m:
        return envelope.agent_id == m.group(1)

    # args_match
    m = re.match(r'args_match\s+"([^"]+)"', condition)
    if m:
        pattern = m.group(1)
        args_str = str(envelope.arguments)
        return bool(re.search(pattern, args_str, re.IGNORECASE))

    # confidence <
    m = re.match(r"confidence\s*<\s*(\d+\.?\d*)", condition)
    if m:
        return envelope.intent.confidence < float(m.group(1))

    return False


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------


class PolicyRule:
    """A single policy rule parsed from YAML."""

    def __init__(self, name: str, condition: str, action: str, severity: str = "medium"):
        self.name = name
        self.condition = condition
        self.action = action  # block, require_approval, warn
        self.severity = severity

    def evaluate(self, envelope: ActionEnvelope) -> Optional[PolicyViolation]:
        """Evaluate rule against an envelope. Returns violation if matched."""
        if _eval_condition(self.condition, envelope):
            return PolicyViolation(
                rule_name=self.name,
                description=f"Condition matched: {self.condition}",
                severity=self.severity,
            )
        return None


# ---------------------------------------------------------------------------
# YAML Policy Engine
# ---------------------------------------------------------------------------


class YAMLPolicyEngine:
    """Loads and evaluates YAML-defined policy rules."""

    def __init__(self):
        self._rules: list[PolicyRule] = []

    def load_yaml(self, yaml_content: str) -> None:
        """Parse YAML policy content and register rules."""
        try:
            import yaml
            data = yaml.safe_load(yaml_content)
        except ImportError:
            # Fallback: minimal YAML-like parser for simple cases
            data = self._minimal_parse(yaml_content)

        if not data or "rules" not in data:
            return

        for rule_data in data["rules"]:
            self._rules.append(PolicyRule(
                name=rule_data.get("name", "unnamed"),
                condition=rule_data.get("condition", ""),
                action=rule_data.get("action", "warn"),
                severity=rule_data.get("severity", "medium"),
            ))

    def load_file(self, path: Path | str) -> None:
        """Load policy from a YAML file."""
        content = Path(path).read_text()
        self.load_yaml(content)

    def add_rule(self, rule: PolicyRule) -> None:
        """Programmatically add a rule."""
        self._rules.append(rule)

    def evaluate(self, envelope: ActionEnvelope) -> PolicyDecision:
        """Evaluate all rules against an action envelope."""
        violations: list[PolicyViolation] = []
        matched_rules: list[str] = []
        requires_approval = False
        blocked = False

        for rule in self._rules:
            violation = rule.evaluate(envelope)
            if violation:
                violations.append(violation)
                matched_rules.append(rule.name)
                if rule.action == "block":
                    blocked = True
                elif rule.action == "require_approval":
                    requires_approval = True

        return PolicyDecision(
            allow=not blocked,
            requires_approval=requires_approval,
            violations=violations,
            evaluated_rules=len(self._rules),
            matched_rules=matched_rules,
        )

    def _minimal_parse(self, content: str) -> dict:
        """Minimal YAML-like parser for when PyYAML is not installed."""
        rules = []
        current_rule: dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- name:"):
                if current_rule:
                    rules.append(current_rule)
                current_rule = {"name": stripped.split(":", 1)[1].strip().strip('"')}
            elif stripped.startswith("condition:") and current_rule:
                current_rule["condition"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("action:") and current_rule:
                current_rule["action"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("severity:") and current_rule:
                current_rule["severity"] = stripped.split(":", 1)[1].strip().strip('"')
        if current_rule:
            rules.append(current_rule)
        return {"rules": rules}
