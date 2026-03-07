"""Tests for notification system."""

import pytest
from agent_preflight.notifications.webhooks import (
    NotificationManager,
    NotificationPayload,
    SlackNotifier,
    TeamsNotifier,
    WebhookNotifier,
)


class FakeNotifier:
    """Test notifier that records sends."""

    def __init__(self, success=True):
        self.sent = []
        self._success = success

    def send(self, payload):
        self.sent.append(payload)
        return self._success


class TestNotificationPayload:
    def test_create_payload(self):
        p = NotificationPayload(
            event_type="action_blocked",
            agent_id="agent-1",
            tool_name="delete_db",
            risk_score=0.95,
            verdict="block",
            summary="Blocked destructive action",
        )
        assert p.event_type == "action_blocked"
        assert p.risk_score == 0.95
        assert p.timestamp != ""


class TestNotificationManager:
    def test_add_and_notify(self):
        mgr = NotificationManager()
        fake = FakeNotifier()
        mgr.add_notifier(fake)

        payload = NotificationPayload(
            event_type="test",
            agent_id="a1",
            tool_name="t1",
            risk_score=0.5,
        )
        results = mgr.notify(payload)
        assert len(fake.sent) == 1
        assert any(v for v in results.values())

    def test_multiple_notifiers(self):
        mgr = NotificationManager()
        f1 = FakeNotifier()
        f2 = FakeNotifier()
        mgr.add_notifier(f1)
        mgr.add_notifier(f2)

        payload = NotificationPayload(event_type="test", agent_id="a1", tool_name="t1")
        mgr.notify(payload)
        assert len(f1.sent) == 1
        assert len(f2.sent) == 1

    def test_notify_blocked_action(self):
        mgr = NotificationManager()
        fake = FakeNotifier()
        mgr.add_notifier(fake)

        mgr.notify_blocked_action("agent-1", "delete_all", 0.95)
        assert len(fake.sent) == 1
        assert fake.sent[0].event_type == "action_blocked"

    def test_notify_high_risk(self):
        mgr = NotificationManager()
        fake = FakeNotifier()
        mgr.add_notifier(fake)

        mgr.notify_high_risk("agent-1", "risky_op", 0.75)
        assert len(fake.sent) == 1
        assert fake.sent[0].event_type == "high_risk"

    def test_history(self):
        mgr = NotificationManager()
        fake = FakeNotifier()
        mgr.add_notifier(fake)

        mgr.notify_blocked_action("a1", "t1", 0.9)
        mgr.notify_high_risk("a1", "t2", 0.7)

        assert len(mgr.history) == 2

    def test_failed_notifier(self):
        mgr = NotificationManager()
        fake = FakeNotifier(success=False)
        mgr.add_notifier(fake)

        results = mgr.notify(NotificationPayload(
            event_type="test", agent_id="a1", tool_name="t1"
        ))
        assert not any(v for v in results.values())


class TestSlackNotifier:
    def test_risk_color(self):
        assert SlackNotifier._risk_color(0.9) == "#d32f2f"
        assert SlackNotifier._risk_color(0.5) == "#ff9800"
        assert SlackNotifier._risk_color(0.3) == "#ffc107"
        assert SlackNotifier._risk_color(0.1) == "#4caf50"

    def test_verdict_icon(self):
        assert "[BLOCKED]" in SlackNotifier._verdict_icon("block")
        assert "[WARNING]" in SlackNotifier._verdict_icon("warn")
        assert "[ALLOWED]" in SlackNotifier._verdict_icon("allow")
