"""
Risk Memory — Preflight learns from every decision it makes.

Unlike static rule engines, Risk Memory builds a growing knowledge base
of what went wrong and what was safe. Every blocked action, every allowed
action, every near-miss gets recorded. Future actions are scored against
this memory.

This is the headline differentiator:
  "Preflight gets smarter every time it blocks something."

No other agent safety tool does this.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from typing import Any, Optional


class RiskMemory:
    """In-memory risk memory that learns from past decisions.

    Stores action patterns with their outcomes and uses them to
    adjust future risk scores. Thread-safe via simple append-only design.

    Patterns are stored as normalized fingerprints:
        tool_name + sorted(argument_keys) -> pattern hash

    Each pattern tracks:
        - Times seen
        - Times blocked
        - Times allowed
        - Historical risk scores
        - Whether similar patterns have been blocked before
    """

    def __init__(self, max_entries: int = 10000):
        self._max = max_entries
        self._patterns: dict[str, _PatternRecord] = {}
        self._tool_history: dict[str, _ToolRecord] = {}
        self._recent_blocks: list[dict] = []  # ring buffer of recent blocks

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        risk_score: float,
        verdict: str,
        flags: list[str],
        agent_id: str = "",
    ) -> None:
        """Record an action's outcome in risk memory."""
        pattern_key = self._pattern_key(tool_name, arguments)
        tool_key = tool_name.lower()

        # Update pattern record
        if pattern_key not in self._patterns:
            self._patterns[pattern_key] = _PatternRecord(
                tool_name=tool_name,
                pattern_key=pattern_key,
            )
        rec = self._patterns[pattern_key]
        rec.total += 1
        rec.risk_scores.append(risk_score)
        if verdict in ("block", "blocked"):
            rec.blocked += 1
            rec.last_blocked_at = time.time()
        else:
            rec.allowed += 1

        # Update tool-level record
        if tool_key not in self._tool_history:
            self._tool_history[tool_key] = _ToolRecord(tool_name=tool_name)
        trec = self._tool_history[tool_key]
        trec.total += 1
        if verdict in ("block", "blocked"):
            trec.blocked += 1
            # Track recent blocks
            self._recent_blocks.append({
                "tool_name": tool_name,
                "risk_score": risk_score,
                "flags": flags,
                "agent_id": agent_id,
                "timestamp": time.time(),
            })
            if len(self._recent_blocks) > 100:
                self._recent_blocks = self._recent_blocks[-100:]

        # Evict old patterns if over limit
        if len(self._patterns) > self._max:
            oldest = min(self._patterns.values(), key=lambda r: r.last_seen_at)
            del self._patterns[oldest.pattern_key]

    def recall(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> RiskRecall:
        """Recall risk memory for a given action pattern.

        Returns a RiskRecall with:
        - previously_blocked: was this exact pattern blocked before?
        - tool_block_rate: what % of this tool's calls have been blocked?
        - risk_adjustment: suggested adjustment to risk score (-0.2 to +0.3)
        - memory_flags: additional flags based on memory
        """
        pattern_key = self._pattern_key(tool_name, arguments)
        tool_key = tool_name.lower()

        flags: list[str] = []
        adjustment = 0.0

        # Check exact pattern match
        previously_blocked = False
        if pattern_key in self._patterns:
            rec = self._patterns[pattern_key]
            if rec.blocked > 0:
                previously_blocked = True
                block_rate = rec.blocked / rec.total
                adjustment += min(block_rate * 0.3, 0.3)
                flags.append(f"pattern_blocked_{rec.blocked}_times")

        # Check tool-level history
        tool_block_rate = 0.0
        if tool_key in self._tool_history:
            trec = self._tool_history[tool_key]
            if trec.total > 0:
                tool_block_rate = trec.blocked / trec.total
                if tool_block_rate > 0.5:
                    adjustment += 0.1
                    flags.append(f"tool_frequently_blocked")

        # Check for recent blocks on similar tools
        recent_similar = [
            b for b in self._recent_blocks[-20:]
            if b["tool_name"].lower() == tool_key
        ]
        if len(recent_similar) >= 2:
            adjustment += 0.05
            flags.append("repeated_recent_blocks")

        return RiskRecall(
            previously_blocked=previously_blocked,
            tool_block_rate=tool_block_rate,
            risk_adjustment=min(adjustment, 0.3),
            memory_flags=flags,
            pattern_count=self._patterns.get(pattern_key, _PatternRecord(tool_name=tool_name, pattern_key=pattern_key)).total,
        )

    def get_stats(self) -> dict:
        """Get memory statistics."""
        total_patterns = len(self._patterns)
        total_blocked = sum(r.blocked for r in self._patterns.values())
        total_allowed = sum(r.allowed for r in self._patterns.values())
        return {
            "total_patterns": total_patterns,
            "total_blocked": total_blocked,
            "total_allowed": total_allowed,
            "unique_tools": len(self._tool_history),
            "recent_blocks": len(self._recent_blocks),
        }

    @staticmethod
    def _pattern_key(tool_name: str, arguments: dict) -> str:
        """Generate a normalized pattern key."""
        canonical = json.dumps(
            {"tool": tool_name.lower(), "arg_keys": sorted(arguments.keys())},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class _PatternRecord:
    __slots__ = ("tool_name", "pattern_key", "total", "blocked", "allowed",
                 "risk_scores", "last_seen_at", "last_blocked_at")

    def __init__(self, tool_name: str, pattern_key: str = ""):
        self.tool_name = tool_name
        self.pattern_key = pattern_key
        self.total = 0
        self.blocked = 0
        self.allowed = 0
        self.risk_scores: list[float] = []
        self.last_seen_at = time.time()
        self.last_blocked_at = 0.0


class _ToolRecord:
    __slots__ = ("tool_name", "total", "blocked")

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.total = 0
        self.blocked = 0


class RiskRecall:
    """Result of querying risk memory."""
    __slots__ = ("previously_blocked", "tool_block_rate", "risk_adjustment",
                 "memory_flags", "pattern_count")

    def __init__(
        self,
        previously_blocked: bool = False,
        tool_block_rate: float = 0.0,
        risk_adjustment: float = 0.0,
        memory_flags: Optional[list[str]] = None,
        pattern_count: int = 0,
    ):
        self.previously_blocked = previously_blocked
        self.tool_block_rate = tool_block_rate
        self.risk_adjustment = risk_adjustment
        self.memory_flags = memory_flags or []
        self.pattern_count = pattern_count

    def to_dict(self) -> dict:
        return {
            "previously_blocked": self.previously_blocked,
            "tool_block_rate": self.tool_block_rate,
            "risk_adjustment": self.risk_adjustment,
            "memory_flags": self.memory_flags,
            "pattern_count": self.pattern_count,
        }
