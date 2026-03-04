"""Tests for ATF Drift Intelligence Engine."""

import pytest
from agent_preflight.atf.database import ATFDatabase
from agent_preflight.atf.drift import DriftIntelligenceEngine, _cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.5]
        assert abs(_cosine_similarity(v, v) - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 0.001

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class TestDriftIntelligenceEngine:
    @pytest.mark.asyncio
    async def test_analyze_empty_history(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        engine = DriftIntelligenceEngine(db)
        result = await engine.analyze("fp1", [0.1, 0.2, 0.3])
        assert result.anomaly_score == 0.5  # Neutral for empty history
        assert not result.is_anomalous

    @pytest.mark.asyncio
    async def test_record_and_analyze(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        engine = DriftIntelligenceEngine(db)

        # Record some history
        for i in range(10):
            await engine.record_outcome(
                f"fp_{i}", [0.1 * i, 0.2, 0.3], 0.3, "allow", False
            )

        result = await engine.analyze("fp_new", [0.1, 0.2, 0.3])
        assert 0 <= result.anomaly_score <= 1

    @pytest.mark.asyncio
    async def test_register_failure_signature(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        engine = DriftIntelligenceEngine(db)

        await engine.register_failure_signature(
            "dangerous_pattern", [0.9, 0.8, 0.7], 0.9
        )

        result = await engine.analyze("fp", [0.9, 0.8, 0.7])
        assert result.similarity_score > 0.5
        assert "dangerous_pattern" in result.similar_actions

    @pytest.mark.asyncio
    async def test_failure_rate_tracking(self):
        db = ATFDatabase(":memory:")
        await db.initialize()
        engine = DriftIntelligenceEngine(db)

        # Record mix of successes and failures
        for i in range(5):
            await engine.record_outcome(
                f"fp_{i}", [0.5, 0.5, 0.5], 0.5, "allow", False
            )
        for i in range(5):
            await engine.record_outcome(
                f"fp_fail_{i}", [0.5, 0.5, 0.5], 0.8, "block", True
            )

        result = await engine.analyze("fp_test", [0.5, 0.5, 0.5])
        assert result.historical_failure_rate >= 0
