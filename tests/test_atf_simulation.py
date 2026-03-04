"""Tests for ATF Probabilistic Simulation Engine."""

import pytest
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
from agent_preflight.atf.simulation import SimulationEngine, PerturbationGenerator
from agent_preflight.atf.plugins.filesystem import FilesystemCascadePlugin
from agent_preflight.atf.plugins.api_cost import APICostExplosionPlugin
from agent_preflight.atf.plugins.dependency import DependencyGraphPlugin
from agent_preflight.atf.plugins.memory import MemoryRunawayPlugin
from agent_preflight.atf.plugins.infrastructure import InfrastructureMutationPlugin


def _make_envelope(tool_name="test_tool", **kwargs):
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name=tool_name,
        arguments=kwargs.get("arguments", {}),
        resource_targets=kwargs.get("targets", []),
        intent=StructuredIntent(
            goal=kwargs.get("goal", "Test"),
            reasoning_summary="Test",
            external_calls=kwargs.get("external_calls", []),
        ),
    )


class TestPerturbationGenerator:
    def test_generates_dict(self):
        p = PerturbationGenerator.generate(seed=42)
        assert "timing_variance" in p
        assert "resource_pressure" in p
        assert "network_latency_ms" in p
        assert "memory_pressure" in p

    def test_deterministic_with_seed(self):
        p1 = PerturbationGenerator.generate(seed=42)
        p2 = PerturbationGenerator.generate(seed=42)
        assert p1 == p2


class TestFilesystemPlugin:
    @pytest.mark.asyncio
    async def test_supports_file_ops(self):
        plugin = FilesystemCascadePlugin()
        e = _make_envelope("file_write")
        assert plugin.supports(e)

    @pytest.mark.asyncio
    async def test_not_supports_api(self):
        plugin = FilesystemCascadePlugin()
        e = _make_envelope("send_email")
        assert not plugin.supports(e)

    @pytest.mark.asyncio
    async def test_detects_dangerous_path(self):
        plugin = FilesystemCascadePlugin()
        e = _make_envelope("file_delete", targets=["/etc/config"])
        p = PerturbationGenerator.generate(seed=1)
        result = await plugin.simulate(e, p)
        assert result.failure_detected
        assert result.cascade_detected


class TestAPICostPlugin:
    @pytest.mark.asyncio
    async def test_supports_api_calls(self):
        plugin = APICostExplosionPlugin()
        e = _make_envelope("api_request")
        assert plugin.supports(e)

    @pytest.mark.asyncio
    async def test_supports_external_calls(self):
        plugin = APICostExplosionPlugin()
        e = _make_envelope("custom_tool", external_calls=["api.example.com"])
        assert plugin.supports(e)


class TestSimulationEngine:
    @pytest.mark.asyncio
    async def test_no_plugins(self):
        engine = SimulationEngine()
        e = _make_envelope("test_tool")
        result = await engine.run_rollouts(e, n=10)
        assert result.rollout_count == 0

    @pytest.mark.asyncio
    async def test_with_filesystem_plugin(self):
        engine = SimulationEngine()
        engine.register_plugin(FilesystemCascadePlugin())
        e = _make_envelope("file_delete", targets=["/etc/config"])
        result = await engine.run_rollouts(e, n=30)
        assert result.rollout_count == 30
        assert result.failure_probability >= 0

    @pytest.mark.asyncio
    async def test_all_plugins(self):
        engine = SimulationEngine()
        for p in [FilesystemCascadePlugin(), APICostExplosionPlugin(),
                   DependencyGraphPlugin(), MemoryRunawayPlugin(),
                   InfrastructureMutationPlugin()]:
            engine.register_plugin(p)

        e = _make_envelope(
            "deploy_infrastructure",
            arguments={"target": "production", "type": "kubernetes"},
            targets=["/prod/cluster"],
        )
        result = await engine.run_rollouts(e, n=50)
        assert result.rollout_count == 50
        assert result.confidence_interval[0] <= result.confidence_interval[1]
