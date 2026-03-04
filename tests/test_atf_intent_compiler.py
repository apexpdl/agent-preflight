"""Tests for ATF Intent Compiler."""

import pytest
from agent_preflight.atf.intent_compiler import IntentCompiler, HashEmbedding
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent


def _make_envelope(goal="Test goal"):
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name="test_tool",
        arguments={},
        intent=StructuredIntent(goal=goal, reasoning_summary="Test"),
    )


class TestHashEmbedding:
    @pytest.mark.asyncio
    async def test_produces_vector(self):
        embedder = HashEmbedding(dimensions=64)
        vec = await embedder.embed("hello world")
        assert len(vec) == 64
        assert all(isinstance(v, float) for v in vec)

    @pytest.mark.asyncio
    async def test_deterministic(self):
        embedder = HashEmbedding()
        v1 = await embedder.embed("test input")
        v2 = await embedder.embed("test input")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_different_inputs_differ(self):
        embedder = HashEmbedding()
        v1 = await embedder.embed("delete all files")
        v2 = await embedder.embed("read user profile")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_normalized(self):
        embedder = HashEmbedding()
        vec = await embedder.embed("some text")
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 0.01


class TestIntentCompiler:
    @pytest.mark.asyncio
    async def test_compile(self):
        compiler = IntentCompiler()
        envelope = _make_envelope("Delete old records")
        compiled = await compiler.compile(envelope)
        assert compiled.intent_hash
        assert len(compiled.embedding) == 64
        assert compiled.tool_name == "test_tool"

    @pytest.mark.asyncio
    async def test_hash_deterministic(self):
        compiler = IntentCompiler()
        e = _make_envelope("Same goal")
        c1 = await compiler.compile(e)
        c2 = await compiler.compile(e)
        assert c1.intent_hash == c2.intent_hash

    @pytest.mark.asyncio
    async def test_to_dict(self):
        compiler = IntentCompiler()
        envelope = _make_envelope()
        compiled = await compiler.compile(envelope)
        d = compiled.to_dict()
        assert "intent_hash" in d
        assert d["embedding_dim"] == 64
