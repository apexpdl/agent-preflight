"""
Agent Behavior Analytics — per-agent tracking and intelligence.

Tracks every agent's behavior over time: mistakes, dangerous patterns,
repeated loops, resource usage. Companies LOVE this — it's the dashboard
data that makes Preflight indispensable.

Dashboard example:
    Agent: CodeAssistant
    Last 24h Actions: 1482
    Blocked: 17
    Modified: 8
    Failures: 3
    Risky attempts: 11
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Optional


class AgentProfile:
    """Behavioral profile for a single agent."""

    __slots__ = (
        "agent_id", "first_seen", "last_seen",
        "total_actions", "blocked_actions", "warned_actions", "allowed_actions",
        "total_risk_score", "max_risk_score",
        "tool_usage", "flag_counts", "recent_actions",
        "failure_count", "loop_detections",
    )

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.total_actions = 0
        self.blocked_actions = 0
        self.warned_actions = 0
        self.allowed_actions = 0
        self.total_risk_score = 0.0
        self.max_risk_score = 0.0
        self.tool_usage: dict[str, int] = defaultdict(int)
        self.flag_counts: dict[str, int] = defaultdict(int)
        self.recent_actions: list[dict[str, Any]] = []  # ring buffer
        self.failure_count = 0
        self.loop_detections = 0

    @property
    def average_risk(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return self.total_risk_score / self.total_actions

    @property
    def block_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return self.blocked_actions / self.total_actions

    @property
    def danger_score(self) -> float:
        """Composite danger score for this agent (0.0-1.0).

        Based on: block rate, average risk, max risk, loop detections.
        """
        score = 0.0
        score += self.block_rate * 0.3
        score += min(self.average_risk, 1.0) * 0.3
        score += min(self.max_risk_score, 1.0) * 0.2
        score += min(self.loop_detections / 5, 1.0) * 0.2
        return min(score, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "total_actions": self.total_actions,
            "blocked_actions": self.blocked_actions,
            "warned_actions": self.warned_actions,
            "allowed_actions": self.allowed_actions,
            "average_risk": round(self.average_risk, 4),
            "max_risk_score": round(self.max_risk_score, 4),
            "block_rate": round(self.block_rate, 4),
            "danger_score": round(self.danger_score, 4),
            "top_tools": dict(sorted(
                self.tool_usage.items(), key=lambda x: -x[1]
            )[:10]),
            "top_flags": dict(sorted(
                self.flag_counts.items(), key=lambda x: -x[1]
            )[:10]),
            "failure_count": self.failure_count,
            "loop_detections": self.loop_detections,
        }


class AgentAnalytics:
    """Per-agent behavior tracking and analytics.

    Usage:
        analytics = AgentAnalytics()

        # Record every action
        analytics.record(
            agent_id="code-assistant",
            tool_name="delete_file",
            risk_score=0.85,
            verdict="block",
            flags=["destructive_tool", "irreversible"],
        )

        # Get agent profile
        profile = analytics.get_profile("code-assistant")
        print(profile.to_dict())

        # Get dashboard summary
        summary = analytics.get_summary()
    """

    def __init__(self, max_recent: int = 50, max_agents: int = 1000):
        self._profiles: dict[str, AgentProfile] = {}
        self._max_recent = max_recent
        self._max_agents = max_agents
        self._global_actions = 0
        self._global_blocked = 0

    def record(
        self,
        agent_id: str,
        tool_name: str,
        risk_score: float,
        verdict: str,
        flags: Optional[list[str]] = None,
        arguments: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record an agent action for analytics."""
        profile = self._get_or_create(agent_id)
        profile.last_seen = time.time()
        profile.total_actions += 1
        profile.total_risk_score += risk_score
        profile.max_risk_score = max(profile.max_risk_score, risk_score)
        profile.tool_usage[tool_name] += 1

        self._global_actions += 1

        if verdict in ("block", "blocked"):
            profile.blocked_actions += 1
            self._global_blocked += 1
        elif verdict in ("warn", "warning"):
            profile.warned_actions += 1
        else:
            profile.allowed_actions += 1

        if flags:
            for flag in flags:
                profile.flag_counts[flag] += 1

        # Record in recent actions ring buffer
        action_record = {
            "tool_name": tool_name,
            "risk_score": risk_score,
            "verdict": verdict,
            "flags": flags or [],
            "timestamp": time.time(),
        }
        profile.recent_actions.append(action_record)
        if len(profile.recent_actions) > self._max_recent:
            profile.recent_actions = profile.recent_actions[-self._max_recent:]

        # Detect loops (same tool called 5+ times in last 10 actions)
        self._detect_loops(profile)

    def get_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """Get the behavioral profile for an agent."""
        return self._profiles.get(agent_id)

    def get_all_profiles(self) -> list[AgentProfile]:
        """Get all agent profiles, sorted by danger score."""
        return sorted(
            self._profiles.values(),
            key=lambda p: p.danger_score,
            reverse=True,
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a dashboard-ready summary of all agent activity."""
        profiles = self.get_all_profiles()
        return {
            "total_agents": len(profiles),
            "total_actions": self._global_actions,
            "total_blocked": self._global_blocked,
            "global_block_rate": round(
                self._global_blocked / max(self._global_actions, 1), 4
            ),
            "agents": [p.to_dict() for p in profiles[:20]],
            "most_dangerous": profiles[0].to_dict() if profiles else None,
            "most_active": max(
                profiles, key=lambda p: p.total_actions
            ).to_dict() if profiles else None,
        }

    def get_risky_agents(self, threshold: float = 0.5) -> list[AgentProfile]:
        """Get agents whose danger score exceeds a threshold."""
        return [
            p for p in self._profiles.values()
            if p.danger_score >= threshold
        ]

    def _get_or_create(self, agent_id: str) -> AgentProfile:
        if agent_id not in self._profiles:
            # Evict oldest if at capacity
            if len(self._profiles) >= self._max_agents:
                oldest = min(
                    self._profiles.values(),
                    key=lambda p: p.last_seen,
                )
                del self._profiles[oldest.agent_id]
            self._profiles[agent_id] = AgentProfile(agent_id)
        return self._profiles[agent_id]

    def _detect_loops(self, profile: AgentProfile) -> None:
        """Detect if an agent is stuck in a loop."""
        recent = profile.recent_actions[-10:]
        if len(recent) < 5:
            return

        tool_counts: dict[str, int] = defaultdict(int)
        for action in recent:
            tool_counts[action["tool_name"]] += 1

        for tool, count in tool_counts.items():
            if count >= 5:
                profile.loop_detections += 1
                break
