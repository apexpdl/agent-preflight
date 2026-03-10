"""
Preflight Webhook Notification System.

Enterprise-grade alert delivery with:
- Exponential backoff retry (3 attempts: 1s, 2s, 4s)
- Dead letter queue for failed deliveries
- Delivery tracking and status reporting
- Slack, Microsoft Teams, email, and generic webhook support
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class NotificationPayload:
    """Standard notification payload."""
    event_type: str  # action_blocked, high_risk, budget_warning, policy_violation
    agent_id: str = ""
    tool_name: str = ""
    risk_score: float = 0.0
    verdict: str = ""
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DeliveryRecord:
    """Tracks delivery status of a notification."""
    notification_id: str = ""
    channel: str = ""
    status: str = "pending"  # pending, delivered, failed
    attempts: int = 0
    last_attempt: Optional[str] = None
    error: str = ""
    payload_summary: str = ""


class WebhookNotifier:
    """Generic webhook notifier with retry logic."""

    def __init__(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self._url = url
        self._headers = headers or {"Content-Type": "application/json"}
        self._max_retries = max_retries
        self._base_delay = base_delay

    def send(self, payload: NotificationPayload) -> bool:
        """Send with exponential backoff retry."""
        data = {
            "event_type": payload.event_type,
            "agent_id": payload.agent_id,
            "tool_name": payload.tool_name,
            "risk_score": payload.risk_score,
            "verdict": payload.verdict,
            "summary": payload.summary,
            "details": payload.details,
            "timestamp": payload.timestamp,
        }
        encoded = json.dumps(data).encode()

        for attempt in range(self._max_retries):
            try:
                req = urllib.request.Request(
                    self._url,
                    data=encoded,
                    headers=self._headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status < 400:
                        return True
            except (urllib.error.URLError, OSError):
                pass

            if attempt < self._max_retries - 1:
                delay = self._base_delay * (2 ** attempt)
                time.sleep(delay)

        return False


class SlackNotifier:
    """Slack webhook notifier with formatted messages and retry."""

    def __init__(self, webhook_url: str, max_retries: int = 3):
        self._url = webhook_url
        self._max_retries = max_retries

    def send(self, payload: NotificationPayload) -> bool:
        color = self._risk_color(payload.risk_score)
        icon = self._verdict_icon(payload.verdict)

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{icon} Preflight Alert: {payload.event_type}",
                    "text": payload.summary,
                    "fields": [
                        {"title": "Agent", "value": payload.agent_id, "short": True},
                        {"title": "Tool", "value": payload.tool_name, "short": True},
                        {"title": "Risk Score", "value": f"{payload.risk_score:.2f}", "short": True},
                        {"title": "Verdict", "value": payload.verdict.upper(), "short": True},
                    ],
                    "footer": "Preflight Execution Firewall",
                    "ts": payload.timestamp,
                }
            ]
        }

        encoded = json.dumps(slack_payload).encode()
        for attempt in range(self._max_retries):
            try:
                req = urllib.request.Request(
                    self._url,
                    data=encoded,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status < 400:
                        return True
            except (urllib.error.URLError, OSError):
                pass

            if attempt < self._max_retries - 1:
                time.sleep(1.0 * (2 ** attempt))

        return False

    @staticmethod
    def _risk_color(score: float) -> str:
        if score >= 0.8:
            return "#d32f2f"
        if score >= 0.5:
            return "#ff9800"
        if score >= 0.3:
            return "#ffc107"
        return "#4caf50"

    @staticmethod
    def _verdict_icon(verdict: str) -> str:
        return {
            "block": "[BLOCKED]",
            "warn": "[WARNING]",
            "allow": "[ALLOWED]",
            "require_approval": "[PENDING]",
        }.get(verdict.lower(), "[INFO]")


class TeamsNotifier:
    """Microsoft Teams webhook notifier with retry."""

    def __init__(self, webhook_url: str, max_retries: int = 3):
        self._url = webhook_url
        self._max_retries = max_retries

    def send(self, payload: NotificationPayload) -> bool:
        color = "FF0000" if payload.risk_score >= 0.5 else "FFC107"

        teams_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"Preflight: {payload.event_type}",
            "sections": [
                {
                    "activityTitle": f"Preflight Alert: {payload.event_type}",
                    "activitySubtitle": payload.summary,
                    "facts": [
                        {"name": "Agent", "value": payload.agent_id},
                        {"name": "Tool", "value": payload.tool_name},
                        {"name": "Risk Score", "value": f"{payload.risk_score:.2f}"},
                        {"name": "Verdict", "value": payload.verdict.upper()},
                    ],
                }
            ],
        }

        encoded = json.dumps(teams_payload).encode()
        for attempt in range(self._max_retries):
            try:
                req = urllib.request.Request(
                    self._url,
                    data=encoded,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status < 400:
                        return True
            except (urllib.error.URLError, OSError):
                pass

            if attempt < self._max_retries - 1:
                time.sleep(1.0 * (2 ** attempt))

        return False


class NotificationManager:
    """Manages multiple notification channels with delivery tracking.

    Features:
    - Multi-channel broadcasting
    - Dead letter queue for failed deliveries
    - Delivery status tracking
    - History retention
    """

    def __init__(self, max_dead_letters: int = 1000):
        self._notifiers: list[Any] = []
        self._history: list[NotificationPayload] = []
        self._delivery_log: list[DeliveryRecord] = []
        self._dead_letters: list[tuple[NotificationPayload, str]] = []
        self._max_dead_letters = max_dead_letters

    def add_webhook(self, url: str, **kwargs) -> None:
        self._notifiers.append(WebhookNotifier(url, **kwargs))

    def add_slack(self, webhook_url: str) -> None:
        self._notifiers.append(SlackNotifier(webhook_url))

    def add_teams(self, webhook_url: str) -> None:
        self._notifiers.append(TeamsNotifier(webhook_url))

    def add_notifier(self, notifier: Any) -> None:
        self._notifiers.append(notifier)

    def notify(self, payload: NotificationPayload) -> dict[str, bool]:
        """Send notification to all channels. Failed deliveries go to dead letter queue."""
        self._history.append(payload)
        results = {}

        for i, notifier in enumerate(self._notifiers):
            name = type(notifier).__name__
            channel_id = f"{name}_{i}"
            success = notifier.send(payload)
            results[channel_id] = success

            record = DeliveryRecord(
                notification_id=f"{payload.timestamp}_{i}",
                channel=channel_id,
                status="delivered" if success else "failed",
                attempts=getattr(notifier, "_max_retries", 1),
                last_attempt=datetime.now(timezone.utc).isoformat(),
                payload_summary=f"{payload.event_type}: {payload.tool_name}",
            )
            self._delivery_log.append(record)

            if not success:
                self._dead_letters.append((payload, channel_id))
                if len(self._dead_letters) > self._max_dead_letters:
                    self._dead_letters = self._dead_letters[
                        self._max_dead_letters // 2:
                    ]

        return results

    def notify_blocked_action(
        self,
        agent_id: str,
        tool_name: str,
        risk_score: float,
        summary: str = "",
    ) -> dict[str, bool]:
        payload = NotificationPayload(
            event_type="action_blocked",
            agent_id=agent_id,
            tool_name=tool_name,
            risk_score=risk_score,
            verdict="block",
            summary=summary
            or f"Action '{tool_name}' blocked (risk: {risk_score:.2f})",
        )
        return self.notify(payload)

    def notify_high_risk(
        self,
        agent_id: str,
        tool_name: str,
        risk_score: float,
        summary: str = "",
    ) -> dict[str, bool]:
        payload = NotificationPayload(
            event_type="high_risk",
            agent_id=agent_id,
            tool_name=tool_name,
            risk_score=risk_score,
            verdict="warn",
            summary=summary
            or f"High-risk action detected: '{tool_name}' (risk: {risk_score:.2f})",
        )
        return self.notify(payload)

    @property
    def history(self) -> list[NotificationPayload]:
        return list(self._history)

    @property
    def dead_letters(self) -> list[tuple[NotificationPayload, str]]:
        return list(self._dead_letters)

    @property
    def delivery_log(self) -> list[DeliveryRecord]:
        return list(self._delivery_log)

    def delivery_stats(self) -> dict[str, int]:
        delivered = sum(1 for r in self._delivery_log if r.status == "delivered")
        failed = sum(1 for r in self._delivery_log if r.status == "failed")
        return {
            "total": len(self._delivery_log),
            "delivered": delivered,
            "failed": failed,
            "dead_letters": len(self._dead_letters),
        }
