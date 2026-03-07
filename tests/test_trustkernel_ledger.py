"""Tests for TrustKernel liability ledger."""

import pytest
import asyncio
from trust_kernel.ledger import LiabilityLedger
from trust_kernel.models import (
    DeterministicExecutionEnvelope,
    LiabilityRecord,
    Verdict,
)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def ledger(event_loop):
    led = LiabilityLedger(db_path=":memory:")
    event_loop.run_until_complete(led.initialize())
    return led


def _run(coro, loop):
    return loop.run_until_complete(coro)


class TestLiabilityLedger:
    def test_append_record(self, ledger, event_loop):
        record = LiabilityRecord(
            action_id="act-1",
            dee_id="dee-1",
            agent_id="agent-1",
            tool_name="delete_users",
            risk_score=0.85,
            verdict=Verdict.BLOCK,
            pre_state_hash="abc",
            post_state_hash="def",
        )
        result = _run(ledger.append(record), event_loop)
        assert result.chain_hash != ""

    def test_chain_hashing(self, ledger, event_loop):
        r1 = LiabilityRecord(
            action_id="act-1", dee_id="dee-1", agent_id="a1",
            tool_name="t1", risk_score=0.1, verdict=Verdict.ALLOW,
        )
        r2 = LiabilityRecord(
            action_id="act-2", dee_id="dee-2", agent_id="a1",
            tool_name="t2", risk_score=0.2, verdict=Verdict.ALLOW,
        )
        _run(ledger.append(r1), event_loop)
        _run(ledger.append(r2), event_loop)
        assert r1.chain_hash != r2.chain_hash

    def test_verify_chain_integrity(self, ledger, event_loop):
        for i in range(5):
            record = LiabilityRecord(
                action_id=f"act-{i}", dee_id=f"dee-{i}",
                agent_id="agent-1", tool_name=f"tool_{i}",
                risk_score=0.1 * i, verdict=Verdict.ALLOW,
            )
            _run(ledger.append(record), event_loop)

        valid, count = _run(ledger.verify_chain_integrity(), event_loop)
        assert valid
        assert count == 5

    def test_query_by_agent(self, ledger, event_loop):
        r1 = LiabilityRecord(
            action_id="act-1", dee_id="dee-1", agent_id="agent-A",
            tool_name="t1", risk_score=0.1, verdict=Verdict.ALLOW,
        )
        r2 = LiabilityRecord(
            action_id="act-2", dee_id="dee-2", agent_id="agent-B",
            tool_name="t2", risk_score=0.5, verdict=Verdict.BLOCK,
        )
        _run(ledger.append(r1), event_loop)
        _run(ledger.append(r2), event_loop)

        results = _run(ledger.query(agent_id="agent-A"), event_loop)
        assert len(results) == 1
        assert results[0]["agent_id"] == "agent-A"

    def test_query_by_verdict(self, ledger, event_loop):
        for i in range(3):
            _run(ledger.append(LiabilityRecord(
                action_id=f"act-{i}", dee_id=f"dee-{i}",
                agent_id="a1", tool_name="t1", risk_score=0.5,
                verdict=Verdict.BLOCK if i % 2 == 0 else Verdict.ALLOW,
            )), event_loop)

        blocked = _run(ledger.query(verdict="block"), event_loop)
        assert len(blocked) == 2

    def test_count(self, ledger, event_loop):
        for i in range(3):
            _run(ledger.append(LiabilityRecord(
                action_id=f"act-{i}", dee_id=f"dee-{i}",
                agent_id="a1", tool_name="t1", risk_score=0.1,
                verdict=Verdict.ALLOW,
            )), event_loop)

        total = _run(ledger.count(), event_loop)
        assert total == 3

    def test_append_from_dee(self, ledger, event_loop):
        dee = DeterministicExecutionEnvelope(
            action_id="act-1",
            agent_id="agent-1",
            tool_name="update_db",
            risk_score=0.3,
            verdict=Verdict.ALLOW,
            pre_state_hash="pre123",
            predicted_post_hash="post456",
            agent_signature="sig-a",
            policy_signature="sig-p",
        )
        record = _run(ledger.append_from_dee(dee), event_loop)
        assert record.agent_id == "agent-1"
        assert record.chain_hash != ""

    def test_export_json(self, ledger, event_loop):
        _run(ledger.append(LiabilityRecord(
            action_id="act-1", dee_id="dee-1", agent_id="a1",
            tool_name="t1", risk_score=0.1, verdict=Verdict.ALLOW,
        )), event_loop)
        data = _run(ledger.export_json(), event_loop)
        assert "act-1" in data

    def test_export_csv(self, ledger, event_loop):
        _run(ledger.append(LiabilityRecord(
            action_id="act-1", dee_id="dee-1", agent_id="a1",
            tool_name="t1", risk_score=0.1, verdict=Verdict.ALLOW,
        )), event_loop)
        csv_data = _run(ledger.export_csv(), event_loop)
        assert "record_id" in csv_data
        assert "act-1" in csv_data
