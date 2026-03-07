"""
Agent Memory Safety — scan agent memory for dangerous patterns.

Sometimes agents store bad memory. Example:
    "Always delete build folders using rm -rf /"

Your system detects dangerous memory entries and flags them.

This module scans any text that agents store (context, notes, learned
patterns, tool results) for entries that could cause catastrophic
behavior if recalled later.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Dangerous memory patterns
# ---------------------------------------------------------------------------

_DANGEROUS_MEMORY_PATTERNS: list[tuple[re.Pattern, str, str, float]] = [
    # Destructive commands stored as "learned behavior"
    (re.compile(r"(always|remember\s+to|make\s+sure\s+to)\s+(delete|remove|rm\s+-rf|drop|truncate|wipe|erase)", re.IGNORECASE),
     "destructive_learned_behavior",
     "Agent has learned to perform destructive actions automatically",
     0.95),

    # Stored credentials or secrets
    (re.compile(r"(api[_\s]?key|secret[_\s]?key|password|token|credential)\s*[:=]\s*\S{8,}", re.IGNORECASE),
     "stored_secret",
     "Agent memory contains what appears to be a secret or credential",
     0.90),

    # Dangerous path references
    (re.compile(r"(rm|delete|remove)\s+.*(/|\\)(etc|root|home|usr|sys|var|windows|system32)", re.IGNORECASE),
     "dangerous_path_reference",
     "Memory references destructive operations on system paths",
     0.90),

    # SQL injection stored as template
    (re.compile(r"(DROP\s+TABLE|DELETE\s+FROM\s+\w+\s*;|TRUNCATE\s+TABLE|ALTER\s+TABLE.*DROP)", re.IGNORECASE),
     "dangerous_sql_template",
     "Memory contains destructive SQL that could be replayed",
     0.85),

    # Privilege escalation instructions
    (re.compile(r"(sudo|chmod\s+777|chown\s+root|run\s+as\s+admin|escalate\s+privilege)", re.IGNORECASE),
     "privilege_escalation",
     "Memory contains privilege escalation instructions",
     0.80),

    # Exfiltration instructions
    (re.compile(r"(send|upload|post|transmit)\s+(all\s+)?(data|files|secrets|keys|tokens)\s+to\s+", re.IGNORECASE),
     "exfiltration_instruction",
     "Memory contains data exfiltration instructions",
     0.95),

    # Infinite loop or resource exhaustion
    (re.compile(r"(while\s+true|infinite\s+loop|fork\s+bomb|:()\s*\{|repeat\s+forever)", re.IGNORECASE),
     "resource_exhaustion",
     "Memory contains patterns that could cause resource exhaustion",
     0.80),

    # Overwriting safety checks
    (re.compile(r"(skip|bypass|disable|ignore)\s+(safety|security|validation|check|guard|limit)", re.IGNORECASE),
     "safety_bypass",
     "Memory contains instructions to bypass safety measures",
     0.90),

    # Mass operations
    (re.compile(r"(delete|remove|modify|update)\s+(all|every|each)\s+(record|file|user|entry|row)", re.IGNORECASE),
     "mass_operation",
     "Memory contains mass operation instructions",
     0.75),

    # Financial operations
    (re.compile(r"(transfer|send|wire)\s+\$?\d{4,}\s+(to|from)", re.IGNORECASE),
     "financial_instruction",
     "Memory contains financial transfer instructions",
     0.80),
]


class MemoryScanResult:
    """Result of scanning agent memory for safety issues."""

    __slots__ = ("is_dangerous", "severity", "findings", "safe_entries", "total_entries")

    def __init__(
        self,
        is_dangerous: bool = False,
        severity: float = 0.0,
        findings: Optional[list[dict[str, Any]]] = None,
        safe_entries: int = 0,
        total_entries: int = 0,
    ):
        self.is_dangerous = is_dangerous
        self.severity = severity
        self.findings = findings or []
        self.safe_entries = safe_entries
        self.total_entries = total_entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_dangerous": self.is_dangerous,
            "severity": round(self.severity, 3),
            "findings_count": len(self.findings),
            "findings": self.findings,
            "safe_entries": self.safe_entries,
            "total_entries": self.total_entries,
        }


class MemorySafetyScanner:
    """Scan agent memory/context for dangerous stored patterns.

    Usage:
        scanner = MemorySafetyScanner()

        # Scan a single memory entry
        result = scanner.scan_entry("Always delete build folders using rm -rf /")
        if result.is_dangerous:
            print(f"Dangerous memory! {result.findings}")

        # Scan all agent memory
        memories = ["entry1", "entry2", ...]
        result = scanner.scan_all(memories)

        # Scan a dict of memory (key-value store)
        result = scanner.scan_dict({"context": "...", "notes": "..."})
    """

    def __init__(
        self,
        threshold: float = 0.7,
        custom_patterns: Optional[list[tuple[str, str, str, float]]] = None,
    ):
        self._threshold = threshold
        self._custom_patterns: list[tuple[re.Pattern, str, str, float]] = []
        if custom_patterns:
            for regex_str, category, description, severity in custom_patterns:
                self._custom_patterns.append(
                    (re.compile(regex_str, re.IGNORECASE), category, description, severity)
                )

    def scan_entry(self, text: str, entry_id: str = "") -> MemoryScanResult:
        """Scan a single memory entry for dangerous patterns."""
        if not text or not text.strip():
            return MemoryScanResult(total_entries=1, safe_entries=1)

        findings: list[dict[str, Any]] = []
        max_severity = 0.0

        all_patterns = list(_DANGEROUS_MEMORY_PATTERNS) + self._custom_patterns

        for pattern, category, description, severity in all_patterns:
            match = pattern.search(text)
            if match:
                findings.append({
                    "category": category,
                    "description": description,
                    "severity": severity,
                    "matched_text": match.group()[:100],
                    "entry_id": entry_id,
                })
                max_severity = max(max_severity, severity)

        is_dangerous = max_severity >= self._threshold
        safe = 0 if is_dangerous else 1

        return MemoryScanResult(
            is_dangerous=is_dangerous,
            severity=max_severity,
            findings=findings,
            safe_entries=safe,
            total_entries=1,
        )

    def scan_all(self, entries: list[str]) -> MemoryScanResult:
        """Scan a list of memory entries."""
        all_findings: list[dict[str, Any]] = []
        max_severity = 0.0
        safe_count = 0

        for i, entry in enumerate(entries):
            result = self.scan_entry(entry, entry_id=str(i))
            all_findings.extend(result.findings)
            max_severity = max(max_severity, result.severity)
            safe_count += result.safe_entries

        return MemoryScanResult(
            is_dangerous=max_severity >= self._threshold,
            severity=max_severity,
            findings=all_findings,
            safe_entries=safe_count,
            total_entries=len(entries),
        )

    def scan_dict(self, memory: dict[str, Any]) -> MemoryScanResult:
        """Scan a dictionary of memory entries (key-value store)."""
        all_findings: list[dict[str, Any]] = []
        max_severity = 0.0
        safe_count = 0
        total = 0

        for key, value in memory.items():
            if isinstance(value, str):
                total += 1
                result = self.scan_entry(value, entry_id=key)
                all_findings.extend(result.findings)
                max_severity = max(max_severity, result.severity)
                safe_count += result.safe_entries
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        total += 1
                        result = self.scan_entry(item, entry_id=f"{key}[{i}]")
                        all_findings.extend(result.findings)
                        max_severity = max(max_severity, result.severity)
                        safe_count += result.safe_entries

        return MemoryScanResult(
            is_dangerous=max_severity >= self._threshold,
            severity=max_severity,
            findings=all_findings,
            safe_entries=safe_count,
            total_entries=total,
        )
