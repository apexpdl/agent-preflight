"""
Intent Compiler — validates, normalizes, and fingerprints structured intent.

Generates lightweight embeddings for drift comparison using a fast
hash-based approach (no external API calls by default). Can be
swapped for real embedding models.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Optional, Protocol

from agent_preflight.atf.models import ActionEnvelope, StructuredIntent


class EmbeddingProvider(Protocol):
    """Interface for pluggable embedding models."""

    async def embed(self, text: str) -> list[float]: ...


class HashEmbedding:
    """Fast deterministic pseudo-embedding using feature hashing.

    Produces a fixed-dimension vector from text using locality-sensitive
    hashing. Not a real semantic embedding, but fast and deterministic
    for drift fingerprinting without external API calls.

    Dimension: 64 floats in [-1, 1].
    """

    def __init__(self, dimensions: int = 64):
        self._dim = dimensions

    async def embed(self, text: str) -> list[float]:
        tokens = text.lower().split()
        vector = [0.0] * self._dim
        for i, token in enumerate(tokens):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
            weight = 1.0 / (1.0 + i * 0.1)  # positional decay
            vector[idx] += sign * weight

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [round(v / norm, 6) for v in vector]


class IntentCompiler:
    """Validates, normalizes, and compiles structured intent.

    Responsibilities:
    - Validate all required fields
    - Normalize structure
    - Generate embedding vector
    - Return compiled intent with metadata
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self._embedder = embedding_provider or HashEmbedding()

    async def compile(self, envelope: ActionEnvelope) -> CompiledIntent:
        """Compile and enrich intent from an action envelope."""
        intent = envelope.intent

        # Generate embedding from intent text
        embed_text = f"{intent.goal} {intent.reasoning_summary} {' '.join(intent.expected_state_changes)}"
        embedding = await self._embedder.embed(embed_text)

        # Compute intent hash
        intent_data = intent.model_dump()
        intent_hash = hashlib.sha256(
            json.dumps(intent_data, sort_keys=True, default=str).encode()
        ).hexdigest()

        return CompiledIntent(
            intent=intent,
            embedding=embedding,
            intent_hash=intent_hash,
            tool_name=envelope.tool_name,
            agent_id=envelope.agent_id,
        )


class CompiledIntent:
    """Intent enriched with embedding and hash after compilation."""

    __slots__ = ("intent", "embedding", "intent_hash", "tool_name", "agent_id")

    def __init__(
        self,
        intent: StructuredIntent,
        embedding: list[float],
        intent_hash: str,
        tool_name: str,
        agent_id: str,
    ):
        self.intent = intent
        self.embedding = embedding
        self.intent_hash = intent_hash
        self.tool_name = tool_name
        self.agent_id = agent_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.model_dump(),
            "embedding_dim": len(self.embedding),
            "intent_hash": self.intent_hash,
            "tool_name": self.tool_name,
            "agent_id": self.agent_id,
        }
