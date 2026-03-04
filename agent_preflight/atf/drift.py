"""
Drift Intelligence Engine — anomaly detection for agent behavior.

Stores action fingerprints and embeddings, detects behavioral drift
using lightweight ML (isolation-forest-style scoring and cosine
similarity). Flags actions that resemble known failure patterns.
"""

from __future__ import annotations

import math
import random
from typing import Any, Optional

from agent_preflight.atf.database import ATFDatabase
from agent_preflight.atf.models import DriftInsight


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class IsolationScorer:
    """Lightweight anomaly scorer inspired by Isolation Forest.

    For each new embedding, computes how "isolated" it is from the
    historical distribution by measuring average distance to random
    subsets of stored embeddings.
    """

    def __init__(self, n_estimators: int = 10, sample_size: int = 20):
        self._n_estimators = n_estimators
        self._sample_size = sample_size

    def score(self, embedding: list[float], history: list[list[float]]) -> float:
        """Return anomaly score in [0, 1]. Higher = more anomalous."""
        if not history:
            return 0.5  # Unknown — neutral score

        scores: list[float] = []
        for _ in range(self._n_estimators):
            sample = random.sample(history, min(self._sample_size, len(history)))
            similarities = [_cosine_similarity(embedding, h) for h in sample]
            avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
            # Low similarity = high anomaly
            scores.append(1.0 - avg_sim)

        return sum(scores) / len(scores)


class DriftIntelligenceEngine:
    """Detects behavioral drift and anomalous action patterns.

    Maintains a store of action embeddings and known failure signatures.
    For each new action, computes:
    - Similarity to known failure patterns
    - Historical failure rate for similar actions
    - Anomaly score relative to normal behavior
    """

    def __init__(self, db: ATFDatabase, anomaly_threshold: float = 0.7):
        self._db = db
        self._anomaly_threshold = anomaly_threshold
        self._scorer = IsolationScorer()

    async def analyze(
        self,
        fingerprint: str,
        embedding: list[float],
        risk_score: float = 0.0,
    ) -> DriftInsight:
        """Analyze an action for drift and anomaly signals."""

        # Get known failure signatures
        signatures = await self._db.get_drift_signatures()
        max_sig_similarity = 0.0
        similar_sigs: list[str] = []
        for sig in signatures:
            sim = _cosine_similarity(embedding, sig["embedding"])
            if sim > max_sig_similarity:
                max_sig_similarity = sim
            if sim > 0.6:
                similar_sigs.append(sig["signature_name"])

        # Get historical embeddings
        all_embeddings = await self._db.get_drift_embeddings(limit=500)
        history_vectors = [e["embedding"] for e in all_embeddings]

        # Compute failure rate for similar past actions
        failures = await self._db.get_drift_embeddings(failures_only=True, limit=200)
        failure_similarities = []
        for f in failures:
            sim = _cosine_similarity(embedding, f["embedding"])
            if sim > 0.5:
                failure_similarities.append(sim)
        historical_failure_rate = (
            len(failure_similarities) / max(len(all_embeddings), 1)
            if failure_similarities
            else 0.0
        )

        # Compute anomaly score (clamped to [0, 1])
        anomaly_score = min(1.0, max(0.0, self._scorer.score(embedding, history_vectors)))

        return DriftInsight(
            similarity_score=round(min(1.0, max_sig_similarity), 4),
            historical_failure_rate=round(min(1.0, historical_failure_rate), 4),
            anomaly_score=round(anomaly_score, 4),
            similar_actions=similar_sigs,
            is_anomalous=anomaly_score >= self._anomaly_threshold,
        )

    async def record_outcome(
        self,
        fingerprint: str,
        embedding: list[float],
        risk_score: float,
        outcome: str,
        is_failure: bool,
        agent_id: str = "",
    ) -> None:
        """Record an action outcome for future drift analysis."""
        await self._db.store_drift_embedding(
            fingerprint=fingerprint,
            embedding=embedding,
            risk_score=risk_score,
            outcome=outcome,
            is_failure=is_failure,
            agent_id=agent_id,
        )

    async def register_failure_signature(
        self, name: str, embedding: list[float], failure_rate: float = 1.0
    ) -> None:
        """Register a known failure pattern for future detection."""
        await self._db.store_drift_signature(name, embedding, failure_rate)
