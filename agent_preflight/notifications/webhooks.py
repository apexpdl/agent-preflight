"""
Webhook notification system for Agent Preflight.

Sends alerts for high-risk actions, blocked actions, budget breaches,
and policy violations via Slack, Microsoft Teams, email, or generic
webhooks.
"""

from __future__ import annotations

import json
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


class WebhookNotifier:
    """Generic webhook notifier."""

    def __init__(self, url: str, headers: Optional[dict[str, str]] = None):
        self._url = url
        self._headers = headers or {"Content-Type": "application/json"}

    def send(self, payload: NotificationPayload) -> bool:
        """Send a notification via webhook."""
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
        try:
            req = urllib.request.Request(
                self._url,
                data=json.dumps(data).encode(),
                headers=self._headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except (urllib.error.URLError, OSError):
            return False


class SlackNotifier:
    """Slack webhook notifier with formatted messages."""

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def send(self, payload: NotificationPayload) -> bool:
        """Send a Slack notification."""
        color = self._risk_color(payload.risk_score)
        icon = self._verdict_icon(payload.verdict)

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{icon} Agent Preflight Alert: {payload.event_type}",
                    "text": payload.summary,
                    "fields": [
                        {"title": "Agent", "value": payload.agent_id, "short": True},
                        {"title": "Tool", "value": payload.tool_name, "short": True},
                        {"title": "Risk Score", "value": f"{payload.risk_score:.2f}", "short": True},
                        {"title": "Verdict", "value": payload.verdict.upper(), "short": True},
                    ],
                    "footer": "OpenAura Agent Preflight",
                    "ts": payload.timestamp,
                }
            ]
        }

        try:
            req = urllib.request.Request(
                self._url,
                data=json.dumps(slack_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except (urllib.error.URLError, OSError):
            return False

    @staticmethod
    def _risk_color(score: float) -> str:
        if score >= 0.8:
            return "#d32f2f"  # Red
        if score >= 0.5:
            return "#ff9800"  # Orange
        if score >= 0.3:
            return "#ffc107"  # Yellow
        return "#4caf50"  # Green

    @staticmethod
    def _verdict_icon(verdict: str) -> str:
        icons = {
            "block": "[BLOCKED]",
            "warn": "[WARNING]",
            "allow": "[ALLOWED]",
            "require_approval": "[PENDING]",
        }
        return icons.get(verdict.lower(), "[INFO]")


class TeamsNotifier:
    """Microsoft Teams webhook notifier."""

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def send(self, payload: NotificationPayload) -> bool:
        """Send a Teams notification."""
        color = "FF0000" if payload.risk_score >= 0.5 else "FFC107"

        teams_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"Agent Preflight: {payload.event_type}",
            "sections": [
                {
                    "activityTitle": f"Agent Preflight Alert: {payload.event_type}",
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

        try:
            req = urllib.request.Request(
                self._url,
                data=json.dumps(teams_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except (urllib.error.URLError, OSError):
            return False


class EmailNotifier:
    """Email notifier using SMTP (requires smtplib)."""

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        from_addr: str = "",
        to_addrs: Optional[list[str]] = None,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
    ):
        self._host = smtp_host
        self._port = smtp_port
        self._from = from_addr
        self._to = to_addrs or []
        self._username = username
        self._password = password
        self._use_tls = use_tls

    def send(self, payload: NotificationPayload) -> bool:
        """Send an email notification."""
        if not self._to:
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText

            subject = f"[OpenAura] {payload.event_type}: {payload.tool_name} (risk: {payload.risk_score:.2f})"
            body = (
                f"Agent Preflight Alert\n"
                f"=====================\n\n"
                f"Event: {payload.event_type}\n"
                f"Agent: {payload.agent_id}\n"
                f"Tool: {payload.tool_name}\n"
                f"Risk Score: {payload.risk_score:.2f}\n"
                f"Verdict: {payload.verdict}\n"
                f"Time: {payload.timestamp}\n\n"
                f"Summary: {payload.summary}\n"
            )

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = ", ".join(self._to)

            with smtplib.SMTP(self._host, self._port) as server:
                if self._use_tls:
                    server.starttls()
                if self._username:
                    server.login(self._username, self._password)
                server.sendmail(self._from, self._to, msg.as_string())

            return True
        except Exception:
            return False


class NotificationManager:
    """Manages multiple notification channels.

    Register notifiers and broadcast alerts to all channels.
    """

    def __init__(self):
        self._notifiers: list[Any] = []
        self._history: list[NotificationPayload] = []

    def add_webhook(self, url: str) -> None:
        self._notifiers.append(WebhookNotifier(url))

    def add_slack(self, webhook_url: str) -> None:
        self._notifiers.append(SlackNotifier(webhook_url))

    def add_teams(self, webhook_url: str) -> None:
        self._notifiers.append(TeamsNotifier(webhook_url))

    def add_email(self, **kwargs) -> None:
        self._notifiers.append(EmailNotifier(**kwargs))

    def add_notifier(self, notifier: Any) -> None:
        self._notifiers.append(notifier)

    def notify(self, payload: NotificationPayload) -> dict[str, bool]:
        """Send notification to all registered channels."""
        self._history.append(payload)
        results = {}
        for i, notifier in enumerate(self._notifiers):
            name = getattr(notifier, "__class__", type(notifier)).__name__
            results[f"{name}_{i}"] = notifier.send(payload)
        return results

    def notify_blocked_action(
        self,
        agent_id: str,
        tool_name: str,
        risk_score: float,
        summary: str = "",
    ) -> dict[str, bool]:
        """Convenience: notify about a blocked action."""
        payload = NotificationPayload(
            event_type="action_blocked",
            agent_id=agent_id,
            tool_name=tool_name,
            risk_score=risk_score,
            verdict="block",
            summary=summary or f"Action '{tool_name}' blocked (risk: {risk_score:.2f})",
        )
        return self.notify(payload)

    def notify_high_risk(
        self,
        agent_id: str,
        tool_name: str,
        risk_score: float,
        summary: str = "",
    ) -> dict[str, bool]:
        """Convenience: notify about a high-risk action."""
        payload = NotificationPayload(
            event_type="high_risk",
            agent_id=agent_id,
            tool_name=tool_name,
            risk_score=risk_score,
            verdict="warn",
            summary=summary or f"High-risk action detected: '{tool_name}' (risk: {risk_score:.2f})",
        )
        return self.notify(payload)

    @property
    def history(self) -> list[NotificationPayload]:
        return list(self._history)
