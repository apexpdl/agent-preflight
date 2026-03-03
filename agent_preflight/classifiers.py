"""
Heuristic classifiers for agent actions.

ClassifierChain runs each classifier in sequence, building up
risk level, action type, reversibility, and warnings.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional, Protocol

from .models import ActionCapture, RiskLevel, ActionType, Reversibility


class ClassifierFn(Protocol):
    def __call__(self, action: ActionCapture) -> ActionCapture: ...


_DELETE_RE = [re.compile(p, re.I) for p in [
    r"\bdelete\b", r"\bdrop\b", r"\bremove\b", r"\btruncate\b",
    r"\bpurge\b", r"\bdestroy\b", r"\bunlink\b",
]]

_WRITE_RE = [re.compile(p, re.I) for p in [
    r"\bwrite\b", r"\bupdate\b", r"\binsert\b", r"\bcreate\b",
    r"\bset\b", r"\bput\b", r"\bpost\b", r"\bpatch\b",
    r"\bsave\b", r"\bmodify\b", r"\balter\b",
]]

_NETWORK_RE = [re.compile(p, re.I) for p in [
    r"\bsend\b", r"\bemail\b", r"\bslack\b", r"\bwebhook\b",
    r"\bnotif", r"\bmessage\b", r"\bsms\b", r"\btweet\b",
    r"\bpublish\b", r"\bbroadcast\b",
]]

_FINANCIAL_RE = [re.compile(p, re.I) for p in [
    r"\bpay\b", r"\btransfer\b", r"\bcharge\b", r"\binvoice\b",
    r"\brefund\b", r"\bpurchase\b", r"\bbuy\b", r"\bbook\b",
    r"\border\b", r"\bsubscri", r"\bwire\b", r"\btransact",
]]

_READ_PREFIXES = {
    "get", "fetch", "read", "list", "search", "query",
    "find", "lookup", "check", "describe", "show",
    "count", "exists", "head", "info", "status",
    "select", "retrieve", "load",
}

_IRREVERSIBLE_NAMES = {
    "send_email", "send_message", "send_sms", "send_slack",
    "send_notification", "publish", "tweet", "post_message",
    "delete_database", "drop_table", "truncate_table",
    "transfer_funds", "wire_transfer", "make_payment",
    "charge_card", "execute_trade", "place_order",
    "deploy", "push_to_production",
}

_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _RISK_ORDER.index(a) >= _RISK_ORDER.index(b) else b


def _match_any(text, patterns):
    return any(p.search(text) for p in patterns)


def _args_text(action):
    parts = []
    for v in action.args.values():
        if isinstance(v, str):
            parts.append(v)
    for v in action.kwargs.values():
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


def name_classifier(action):
    name = action.name.lower()
    # Split on underscores so we match individual words
    # e.g. "delete_old_records" -> ["delete", "old", "records"]
    parts = re.split(r"[_\s]+", name)
    parts_text = " ".join(parts)  # "delete old records" - now \b works

    if parts[0] in _READ_PREFIXES:
        action.action_type = ActionType.READ
        action.risk_level = RiskLevel.LOW
        action.reversibility = Reversibility.REVERSIBLE
        return action

    if _match_any(parts_text, _FINANCIAL_RE):
        action.action_type = ActionType.EXECUTE
        action.risk_level = RiskLevel.CRITICAL
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_reasons.append("Financial transaction detected")
        return action

    if _match_any(parts_text, _DELETE_RE):
        action.action_type = ActionType.DELETE
        action.risk_level = RiskLevel.HIGH
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_reasons.append("Destructive operation")
        return action

    if _match_any(parts_text, _NETWORK_RE):
        action.action_type = ActionType.WRITE
        action.risk_level = RiskLevel.MEDIUM
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_reasons.append("External communication - cannot be unsent")
        return action

    if _match_any(parts_text, _WRITE_RE):
        action.action_type = ActionType.WRITE
        action.risk_level = RiskLevel.MEDIUM
        action.reversibility = Reversibility.REVERSIBLE
        return action

    if name in _IRREVERSIBLE_NAMES:
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_level = _max_risk(action.risk_level, RiskLevel.HIGH)

    return action


def args_classifier(action):
    text = _args_text(action)
    if not text:
        return action

    if re.search(r"\b(DROP|TRUNCATE|ALTER)\s+(TABLE|DATABASE|SCHEMA)\b", text, re.I):
        action.risk_level = RiskLevel.CRITICAL
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_reasons.append("Dangerous SQL: schema-altering operation")

    elif re.search(r"DELETE\s+FROM\s+\w+\s*(;|\s*$)", text, re.I):
        if not re.search(r"\bWHERE\b", text, re.I):
            action.risk_level = RiskLevel.CRITICAL
            action.risk_reasons.append("DELETE without WHERE - affects all rows")

    if _match_any(text, _DELETE_RE) and action.action_type != ActionType.DELETE:
        action.risk_level = _max_risk(action.risk_level, RiskLevel.HIGH)
        action.risk_reasons.append("Arguments contain destructive keywords")

    if _match_any(text, _FINANCIAL_RE):
        action.risk_level = _max_risk(action.risk_level, RiskLevel.HIGH)
        if "financial" not in " ".join(action.risk_reasons).lower():
            action.risk_reasons.append("Arguments reference financial operation")

    return action


def known_names_classifier(action):
    if action.name.lower() in _IRREVERSIBLE_NAMES:
        action.reversibility = Reversibility.IRREVERSIBLE
        action.risk_level = _max_risk(action.risk_level, RiskLevel.HIGH)
    return action


class ClassifierChain:
    def __init__(self):
        self._classifiers = [
            name_classifier,
            args_classifier,
            known_names_classifier,
        ]

    def add(self, classifier):
        self._classifiers.append(classifier)
        return self

    def classify(self, action):
        for clf in self._classifiers:
            action = clf(action)
        return action
