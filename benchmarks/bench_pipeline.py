"""
Preflight Performance Benchmark Suite.

Measures latency at p50/p95/p99 for all critical execution paths.
Run with: python -m pytest benchmarks/ -v --tb=short
"""

from __future__ import annotations

import asyncio
import math
import statistics
import time
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(data: list[float], p: float) -> float:
    """Compute the p-th percentile of a sorted list."""
    if not data:
        return 0.0
    k = (len(data) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    return data[f] * (c - k) + data[c] * (k - f)


def _bench(fn, iterations: int = 200) -> dict[str, float]:
    """Run a sync function N times and return latency stats."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return {
        "p50_ms": round(_percentile(times, 50), 3),
        "p95_ms": round(_percentile(times, 95), 3),
        "p99_ms": round(_percentile(times, 99), 3),
        "mean_ms": round(statistics.mean(times), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "iterations": iterations,
    }


async def _async_bench(fn, iterations: int = 200) -> dict[str, float]:
    """Run an async function N times and return latency stats."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await fn()
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return {
        "p50_ms": round(_percentile(times, 50), 3),
        "p95_ms": round(_percentile(times, 95), 3),
        "p99_ms": round(_percentile(times, 99), 3),
        "mean_ms": round(statistics.mean(times), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "iterations": iterations,
    }


def _print_bench(name: str, stats: dict[str, float]) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(f"  p50:  {stats['p50_ms']:.3f} ms")
    print(f"  p95:  {stats['p95_ms']:.3f} ms")
    print(f"  p99:  {stats['p99_ms']:.3f} ms")
    print(f"  mean: {stats['mean_ms']:.3f} ms")
    print(f"  min:  {stats['min_ms']:.3f} ms  max: {stats['max_ms']:.3f} ms")
    print(f"  iterations: {stats['iterations']}")


# ---------------------------------------------------------------------------
# Crypto Benchmarks
# ---------------------------------------------------------------------------

class TestCryptoBenchmarks:
    """Benchmark cryptographic operations."""

    def test_hmac_sign_verify(self):
        from trust_kernel.crypto import CryptoProvider
        cp = CryptoProvider(hmac_key="bench-key-000")
        data = b"benchmark payload for signing verification"

        def sign_and_verify():
            sig = cp.sign(data)
            assert cp.verify_signature(data, sig)

        stats = _bench(sign_and_verify, iterations=500)
        _print_bench("HMAC Sign + Verify", stats)
        assert stats["p99_ms"] < 5.0, f"HMAC sign+verify p99 too slow: {stats['p99_ms']}ms"

    def test_receipt_creation(self):
        from trust_kernel.crypto import CryptoProvider
        cp = CryptoProvider(hmac_key="bench-key-001")

        def create_receipt():
            cp.create_receipt(
                action_id="act-bench-001",
                agent_id="agent-bench",
                pre_state_hash="aabbcc",
                post_state_hash="ddeeff",
                verdict="allow",
                risk_score=0.15,
            )

        stats = _bench(create_receipt, iterations=500)
        _print_bench("Receipt Creation", stats)
        assert stats["p99_ms"] < 10.0

    def test_chain_hash(self):
        from trust_kernel.crypto import CryptoProvider
        cp = CryptoProvider(hmac_key="bench-key-002")

        prev = "0" * 64
        def chain():
            nonlocal prev
            prev = cp.chain_hash(prev, f"record-data-{prev[:8]}")

        stats = _bench(chain, iterations=1000)
        _print_bench("Chain Hash", stats)
        assert stats["p99_ms"] < 2.0


# ---------------------------------------------------------------------------
# Risk Engine Benchmarks
# ---------------------------------------------------------------------------

class TestRiskEngineBenchmarks:
    """Benchmark risk scoring."""

    def test_risk_scoring(self):
        from agent_preflight.atf.risk_engine import RiskEngine
        from agent_preflight.atf.models import ActionEnvelope, StructuredIntent

        engine = RiskEngine()
        envelope = ActionEnvelope(
            agent_id="bench-agent",
            tool_name="file_write",
            arguments={"path": "/tmp/test.txt", "content": "hello"},
            intent=StructuredIntent(
                goal="Write test file",
                reasoning_summary="Benchmark test",
                expected_state_changes=["create /tmp/test.txt"],
                external_calls=[],
                irreversible=False,
                estimated_cost=0.0,
                confidence=0.9,
            ),
        )

        def score():
            engine.assess(envelope)

        stats = _bench(score, iterations=500)
        _print_bench("Risk Scoring (per action)", stats)
        assert stats["p99_ms"] < 20.0, f"Risk scoring p99 too slow: {stats['p99_ms']}ms"


# ---------------------------------------------------------------------------
# Ledger Benchmarks
# ---------------------------------------------------------------------------

class TestLedgerBenchmarks:
    """Benchmark ledger operations."""

    @pytest.mark.asyncio
    async def test_ledger_append(self):
        from trust_kernel.ledger import LiabilityLedger

        ledger = LiabilityLedger(db_path=":memory:")
        await ledger.initialize()

        async def append():
            await ledger.append(
                action_id="act-bench",
                agent_id="agent-bench",
                tool_name="test_tool",
                arguments={"key": "value"},
                verdict="allow",
                risk_score=0.2,
                intent_hash="abc123",
            )

        stats = await _async_bench(append, iterations=300)
        _print_bench("Ledger Append", stats)
        assert stats["p99_ms"] < 50.0

    @pytest.mark.asyncio
    async def test_ledger_query(self):
        from trust_kernel.ledger import LiabilityLedger

        ledger = LiabilityLedger(db_path=":memory:")
        await ledger.initialize()

        # Seed data
        for i in range(100):
            await ledger.append(
                action_id=f"act-{i}",
                agent_id="agent-bench",
                tool_name="test_tool",
                arguments={"i": i},
                verdict="allow" if i % 3 else "block",
                risk_score=i / 100,
                intent_hash=f"hash-{i}",
            )

        async def query():
            await ledger.query(limit=50)

        stats = await _async_bench(query, iterations=200)
        _print_bench("Ledger Query (50 records from 100)", stats)
        assert stats["p99_ms"] < 100.0


# ---------------------------------------------------------------------------
# Snapshot Benchmarks
# ---------------------------------------------------------------------------

class TestSnapshotBenchmarks:
    """Benchmark snapshot generation."""

    def test_html_generation(self):
        from trust_kernel.snapshot import SafetySnapshot

        snap = SafetySnapshot(period_label="Benchmark Run")
        for i in range(50):
            snap.add_action(
                verdict=["allow", "warn", "block"][i % 3],
                risk_score=i / 50,
                tool_name=f"tool_{i}",
                cost_prevented=10.0 if i % 3 == 2 else 0.0,
                pipeline_ms=5.0 + i * 0.1,
            )

        def gen_html():
            snap.generate_html()

        stats = _bench(gen_html, iterations=200)
        _print_bench("Safety Snapshot HTML Generation", stats)
        assert stats["p99_ms"] < 20.0

    def test_badge_svg_generation(self):
        from trust_kernel.snapshot import SafetySnapshot

        snap = SafetySnapshot()
        for i in range(20):
            snap.add_action(verdict="allow", risk_score=0.1, pipeline_ms=3.0)

        def gen_badge():
            snap.generate_badge_svg()

        stats = _bench(gen_badge, iterations=500)
        _print_bench("SVG Badge Generation", stats)
        assert stats["p99_ms"] < 5.0


# ---------------------------------------------------------------------------
# Observability Benchmarks
# ---------------------------------------------------------------------------

class TestObservabilityBenchmarks:
    """Benchmark observability layer."""

    def test_structured_logging(self):
        from trust_kernel.observability import StructuredLogger
        import logging

        logger = StructuredLogger(name="bench", level=logging.CRITICAL)

        def log_entry():
            logger.info("bench_event", agent_id="bench", risk=0.5, tool="test")

        stats = _bench(log_entry, iterations=1000)
        _print_bench("Structured Log Entry", stats)
        assert stats["p99_ms"] < 5.0

    def test_metrics_recording(self):
        from trust_kernel.observability import MetricsCollector

        mc = MetricsCollector()

        def record():
            mc.record_action(
                verdict="allow", risk_score=0.3, pipeline_ms=5.0,
                tool_name="bench_tool", agent_id="bench",
            )

        stats = _bench(record, iterations=1000)
        _print_bench("Metrics Record Action", stats)
        assert stats["p99_ms"] < 2.0

    def test_prometheus_export(self):
        from trust_kernel.observability import MetricsCollector

        mc = MetricsCollector()
        for i in range(100):
            mc.record_action(
                verdict=["allow", "block"][i % 2],
                risk_score=i / 100,
                pipeline_ms=5.0 + i,
                tool_name=f"tool_{i % 5}",
            )

        def export():
            mc.export_prometheus()

        stats = _bench(export, iterations=100)
        _print_bench("Prometheus Export (100 actions)", stats)
        assert stats["p99_ms"] < 50.0


# ---------------------------------------------------------------------------
# Multi-tenancy Benchmarks
# ---------------------------------------------------------------------------

class TestMultitenancyBenchmarks:
    """Benchmark multi-tenant operations."""

    def test_tenant_creation(self):
        from trust_kernel.multitenancy import TenantManager

        tm = TenantManager()

        def create():
            tm.create_tenant(name="bench-tenant", tier="pro")

        stats = _bench(create, iterations=500)
        _print_bench("Tenant Creation", stats)
        assert stats["p99_ms"] < 5.0

    def test_token_auth(self):
        from trust_kernel.multitenancy import TenantManager

        tm = TenantManager()
        tenant, _ = tm.create_tenant(name="auth-bench", tier="enterprise")
        _, raw_token = tm.create_token(tenant.tenant_id, name="bench-token")

        def auth():
            tm.authenticate_token(raw_token)

        stats = _bench(auth, iterations=500)
        _print_bench("Token Authentication", stats)
        assert stats["p99_ms"] < 5.0

    def test_rbac_check(self):
        from trust_kernel.multitenancy import TenantManager, RBACManager

        tm = TenantManager()
        rbac = RBACManager()
        tenant, _ = tm.create_tenant(name="rbac-bench")
        rbac.bind_user("user-1", tenant.tenant_id, role="operator")

        def check():
            rbac.check_access("user-1", tenant.tenant_id, "execute")

        stats = _bench(check, iterations=1000)
        _print_bench("RBAC Permission Check", stats)
        assert stats["p99_ms"] < 1.0
