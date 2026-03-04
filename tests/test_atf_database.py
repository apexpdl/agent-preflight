"""Tests for ATF Database layer."""

import pytest
from agent_preflight.atf.database import ATFDatabase


class TestATFDatabase:
    @pytest.mark.asyncio
    async def test_initialize(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        stats = await db.get_stats()
        assert stats["total_actions"] == 0
        await db.close()

    @pytest.mark.asyncio
    async def test_store_and_get_passport(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        await db.store_passport({
            "passport_id": "p1",
            "action_id": "a1",
            "agent_id": "agent1",
            "tool_name": "tool1",
            "intent_hash": "hash1",
            "risk_score": 0.5,
            "policy_status": "approved",
            "mirror_executed": False,
            "verdict": "allow",
            "human_summary": "Test",
            "signature": "sig123",
            "timestamp": "2025-01-01T00:00:00",
        })
        passports = await db.get_passports(limit=10)
        assert len(passports) == 1
        assert passports[0]["passport_id"] == "p1"

    @pytest.mark.asyncio
    async def test_store_risk(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        await db.store_risk("a1", {
            "score": 0.7,
            "flags": ["test"],
            "requires_mirror": True,
            "breakdown": {"test": 0.7},
        })
        # No query method for risk specifically, but it shouldn't raise
        await db.close()

    @pytest.mark.asyncio
    async def test_drift_embeddings(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        await db.store_drift_embedding("fp1", [0.1, 0.2], 0.5, "allow", False, "agent1")
        embeddings = await db.get_drift_embeddings()
        assert len(embeddings) == 1
        assert embeddings[0]["embedding"] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_pipeline_logs(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        await db.store_pipeline_log({
            "action_id": "a1",
            "agent_id": "agent1",
            "tool_name": "tool1",
            "verdict": "allow",
            "risk_score": 0.3,
            "pipeline_time_ms": 50,
            "full_result": {"test": True},
        })
        logs = await db.get_pipeline_logs()
        assert len(logs) == 1
        assert logs[0]["full_result"]["test"] is True

    @pytest.mark.asyncio
    async def test_stats(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        for v in ["allow", "allow", "block"]:
            await db.store_pipeline_log({
                "action_id": f"a_{v}",
                "agent_id": "agent1",
                "tool_name": "tool1",
                "verdict": v,
                "risk_score": 0.5 if v == "block" else 0.2,
                "pipeline_time_ms": 100,
                "full_result": {},
            })
        stats = await db.get_stats()
        assert stats["total_actions"] == 3
        assert stats["blocked_actions"] == 1
