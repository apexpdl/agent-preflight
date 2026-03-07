"""
TrustKernel Liability Ledger.

Append-only, tamper-proof, cryptographically signed record of every
action. Each record links to the previous via chain hashing, creating
an auditable chain of custody for all AI agent actions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trust_kernel.crypto import CryptoProvider
from trust_kernel.models import (
    DeterministicExecutionEnvelope,
    LiabilityRecord,
    Verdict,
)


class LiabilityLedger:
    """Append-only liability ledger with chain hashing.

    Every record is:
    - Cryptographically signed
    - Chain-linked to the previous record (tamper-evident)
    - Queryable by agent, risk, timestamp, action type
    - Exportable to JSON/CSV for auditors
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS liability_ledger (
        record_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        dee_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        operator_id TEXT,
        tool_name TEXT NOT NULL,
        risk_score REAL NOT NULL,
        verdict TEXT NOT NULL,
        pre_state_hash TEXT,
        post_state_hash TEXT,
        agent_signature TEXT,
        operator_signature TEXT,
        policy_signature TEXT,
        chain_hash TEXT NOT NULL,
        metadata TEXT,
        timestamp TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_ledger_agent ON liability_ledger(agent_id);
    CREATE INDEX IF NOT EXISTS idx_ledger_ts ON liability_ledger(timestamp);
    CREATE INDEX IF NOT EXISTS idx_ledger_verdict ON liability_ledger(verdict);
    CREATE INDEX IF NOT EXISTS idx_ledger_risk ON liability_ledger(risk_score);
    CREATE INDEX IF NOT EXISTS idx_ledger_chain ON liability_ledger(chain_hash);

    CREATE TABLE IF NOT EXISTS consensus_requests (
        request_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        dee_id TEXT,
        agent_id TEXT,
        tool_name TEXT,
        risk_score REAL,
        required_approvals INTEGER NOT NULL DEFAULT 1,
        collected_approvals INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        expires_at TEXT,
        summary TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS consensus_votes (
        vote_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL,
        operator_id TEXT NOT NULL,
        approved INTEGER NOT NULL,
        signature TEXT,
        reason TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES consensus_requests(request_id)
    );

    CREATE TABLE IF NOT EXISTS replay_manifests (
        manifest_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        dee_id TEXT,
        model_version TEXT,
        model_seed INTEGER,
        temperature REAL,
        pre_state_snapshot TEXT,
        envelope_data TEXT,
        expected_result TEXT,
        timestamp TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        crypto: Optional[CryptoProvider] = None,
    ):
        self._db_path = str(db_path)
        self._crypto = crypto or CryptoProvider()
        self._conn: Optional[sqlite3.Connection] = None
        self._last_chain_hash = "genesis"

    async def initialize(self) -> None:
        """Create tables and load the latest chain hash."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

        # Load last chain hash for continuity
        row = self._conn.execute(
            "SELECT chain_hash FROM liability_ledger ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row:
            self._last_chain_hash = row["chain_hash"]

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("Ledger not initialized. Call initialize() first.")
        return self._conn

    # -- Append record -----------------------------------------------------

    async def append(self, record: LiabilityRecord) -> LiabilityRecord:
        """Append a record to the ledger with chain hashing."""
        conn = self._ensure_conn()

        # Compute chain hash linking to previous record
        record.compute_chain_hash(self._last_chain_hash)
        self._last_chain_hash = record.chain_hash

        conn.execute(
            """INSERT INTO liability_ledger
               (record_id, action_id, dee_id, agent_id, operator_id,
                tool_name, risk_score, verdict, pre_state_hash, post_state_hash,
                agent_signature, operator_signature, policy_signature,
                chain_hash, metadata, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.record_id,
                record.action_id,
                record.dee_id,
                record.agent_id,
                record.operator_id,
                record.tool_name,
                record.risk_score,
                record.verdict.value,
                record.pre_state_hash,
                record.post_state_hash,
                record.agent_signature,
                record.operator_signature,
                record.policy_signature,
                record.chain_hash,
                json.dumps(record.metadata),
                record.timestamp.isoformat(),
            ),
        )
        conn.commit()
        return record

    async def append_from_dee(
        self,
        dee: DeterministicExecutionEnvelope,
        operator_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> LiabilityRecord:
        """Create and append a record from a DEE."""
        record = LiabilityRecord(
            action_id=dee.action_id,
            dee_id=dee.dee_id,
            agent_id=dee.agent_id,
            tool_name=dee.tool_name,
            risk_score=dee.risk_score,
            verdict=dee.verdict,
            pre_state_hash=dee.pre_state_hash,
            post_state_hash=dee.actual_post_hash or dee.predicted_post_hash,
            agent_signature=dee.agent_signature,
            operator_signature=dee.operator_signature,
            policy_signature=dee.policy_signature,
            operator_id=operator_id,
            metadata=metadata or {},
        )
        return await self.append(record)

    # -- Query -------------------------------------------------------------

    async def query(
        self,
        agent_id: Optional[str] = None,
        verdict: Optional[str] = None,
        min_risk: Optional[float] = None,
        max_risk: Optional[float] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query the ledger with filters."""
        conn = self._ensure_conn()
        query = "SELECT * FROM liability_ledger WHERE 1=1"
        params: list[Any] = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if verdict:
            query += " AND verdict = ?"
            params.append(verdict)
        if min_risk is not None:
            query += " AND risk_score >= ?"
            params.append(min_risk)
        if max_risk is not None:
            query += " AND risk_score <= ?"
            params.append(max_risk)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        if until:
            query += " AND timestamp <= ?"
            params.append(until)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("metadata"):
                d["metadata"] = json.loads(d["metadata"])
            results.append(d)
        return results

    async def get_record(self, record_id: str) -> Optional[dict[str, Any]]:
        """Get a single record by ID."""
        conn = self._ensure_conn()
        row = conn.execute(
            "SELECT * FROM liability_ledger WHERE record_id = ?", (record_id,)
        ).fetchone()
        if row:
            d = dict(row)
            if d.get("metadata"):
                d["metadata"] = json.loads(d["metadata"])
            return d
        return None

    async def count(self, verdict: Optional[str] = None) -> int:
        """Count records, optionally filtered by verdict."""
        conn = self._ensure_conn()
        if verdict:
            row = conn.execute(
                "SELECT COUNT(*) FROM liability_ledger WHERE verdict = ?",
                (verdict,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM liability_ledger").fetchone()
        return row[0] if row else 0

    # -- Chain integrity verification --------------------------------------

    async def verify_chain_integrity(self) -> tuple[bool, int]:
        """Verify the integrity of the entire chain.

        Returns (is_valid, verified_count).
        """
        conn = self._ensure_conn()
        rows = conn.execute(
            "SELECT * FROM liability_ledger ORDER BY created_at ASC"
        ).fetchall()

        if not rows:
            return True, 0

        previous_hash = "genesis"
        verified = 0

        for row in rows:
            record = LiabilityRecord(
                record_id=row["record_id"],
                action_id=row["action_id"],
                dee_id=row["dee_id"],
                agent_id=row["agent_id"],
                tool_name=row["tool_name"],
                risk_score=row["risk_score"],
                verdict=Verdict(row["verdict"]),
                pre_state_hash=row["pre_state_hash"] or "",
                post_state_hash=row["post_state_hash"] or "",
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            expected_hash = record.compute_chain_hash(previous_hash)
            if expected_hash != row["chain_hash"]:
                return False, verified
            previous_hash = row["chain_hash"]
            verified += 1

        return True, verified

    # -- Export ------------------------------------------------------------

    async def export_json(self, limit: int = 10000) -> str:
        """Export ledger records as JSON for auditors."""
        records = await self.query(limit=limit)
        return json.dumps(records, indent=2, default=str)

    async def export_csv(self, limit: int = 10000) -> str:
        """Export ledger records as CSV."""
        records = await self.query(limit=limit)
        if not records:
            return ""

        headers = [
            "record_id", "action_id", "dee_id", "agent_id", "tool_name",
            "risk_score", "verdict", "pre_state_hash", "post_state_hash",
            "chain_hash", "timestamp",
        ]
        lines = [",".join(headers)]
        for r in records:
            values = [str(r.get(h, "")) for h in headers]
            lines.append(",".join(values))
        return "\n".join(lines)

    # -- Consensus store ---------------------------------------------------

    async def store_consensus_request(self, data: dict[str, Any]) -> None:
        """Store a consensus request."""
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO consensus_requests
               (request_id, action_id, dee_id, agent_id, tool_name,
                risk_score, required_approvals, collected_approvals,
                status, expires_at, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["request_id"], data["action_id"], data.get("dee_id", ""),
                data.get("agent_id", ""), data.get("tool_name", ""),
                data.get("risk_score", 0), data.get("required_approvals", 1),
                data.get("collected_approvals", 0), data.get("status", "pending"),
                data.get("expires_at"), data.get("summary", ""),
            ),
        )
        conn.commit()

    async def store_consensus_vote(self, data: dict[str, Any]) -> None:
        """Store a consensus vote."""
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO consensus_votes
               (vote_id, request_id, operator_id, approved, signature, reason, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["vote_id"], data["request_id"], data["operator_id"],
                int(data.get("approved", False)), data.get("signature", ""),
                data.get("reason", ""), data.get("timestamp", ""),
            ),
        )
        conn.commit()

    async def get_pending_requests(self) -> list[dict[str, Any]]:
        """Get all pending consensus requests."""
        conn = self._ensure_conn()
        rows = conn.execute(
            "SELECT * FROM consensus_requests WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Replay manifests --------------------------------------------------

    async def store_replay_manifest(self, data: dict[str, Any]) -> None:
        """Store a replay manifest for reproducibility."""
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO replay_manifests
               (manifest_id, action_id, dee_id, model_version, model_seed,
                temperature, pre_state_snapshot, envelope_data, expected_result, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["manifest_id"], data["action_id"], data.get("dee_id", ""),
                data.get("model_version", ""), data.get("model_seed", 0),
                data.get("temperature", 0.0),
                json.dumps(data.get("pre_state_snapshot", {})),
                json.dumps(data.get("envelope_data", {})),
                json.dumps(data.get("expected_result", {})),
                data.get("timestamp", ""),
            ),
        )
        conn.commit()

    async def get_replay_manifest(self, action_id: str) -> Optional[dict[str, Any]]:
        """Get a replay manifest by action ID."""
        conn = self._ensure_conn()
        row = conn.execute(
            "SELECT * FROM replay_manifests WHERE action_id = ?", (action_id,)
        ).fetchone()
        if row:
            d = dict(row)
            for key in ("pre_state_snapshot", "envelope_data", "expected_result"):
                if d.get(key):
                    d[key] = json.loads(d[key])
            return d
        return None
