"""Tests for enterprise webhook reliability."""

import pytest
from agent_preflight.notifications.webhooks import NotificationManager


class TestWebhookDelivery:
    def test_add_webhook(self):
        nm = NotificationManager()
        nm.add_webhook("http://example.com/hook")
        assert len(nm._notifiers) == 1

    def test_delivery_stats_initial(self):
        nm = NotificationManager()
        stats = nm.delivery_stats()
        assert stats["total"] == 0
        assert stats["delivered"] == 0
        assert stats["failed"] == 0

    def test_multiple_channels(self):
        nm = NotificationManager()
        nm.add_webhook("http://example.com/a")
        nm.add_webhook("http://example.com/b")
        assert len(nm._notifiers) == 2
