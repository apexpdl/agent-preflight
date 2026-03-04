"""
Async SQLite database layer for the ATF pipeline.

Stores risk assessments, passports, drift embeddings, and audit data.
Uses aiosqlite for non-blocking IO.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS passports (
    passport_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    intent_hash TEXT NOT NULL,
    risk_score REAL NOT NULL,
    simulation_risk REAL,
    drift_score REAL,
    policy_status TEXT NOT NULL,
    mirror_executed INTEGER NOT NULL DEFAULT 0,
    mirror_matched INTEGER,
    verdict TEXT NOT NULL,
    human_summary TEXT,
    signature TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_passports_agent ON passports(agent_id);
CREATE INDEX IF NOT EXISTS idx_passports_ts ON passports(timestamp);
CREATE INDEX IF NOT EXISTS idx_passports_risk ON passports(risk_score);

CREATE TABLE IF NOT EXISTS risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    score REAL NOT NULL,
    flags TEXT NOT NULL,
    requires_mirror INTEGER NOT NULL,
    breakdown TEXT NOT NULL,
    computation_time_ms REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_risk_action ON risk_assessments(action_id);

CREATE TABLE IF NOT EXISTS drift_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_fingerprint TEXT NOT NULL,
    embedding TEXT NOT NULL,
    risk_score REAL,
    outcome TEXT,
    is_failure INTEGER NOT NULL DEFAULT 0,
    agent_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_drift_fp ON drift_embeddings(action_fingerprint);
CREATE INDEX IF NOT EXISTS idx_drift_failure ON drift_embeddings(is_failure);

CREATE TABLE IF NOT EXISTS drift_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_name TEXT NOT NULL,
    embedding TEXT NOT NULL,
    failure_rate REAL NOT NULL DEFAULT 0.0,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    verdict TEXT NOT NULL,
    risk_score REAL NOT NULL,
    pipeline_time_ms REAL,
    full_result TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_ts ON pipeline_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_verdict ON pipeline_logs(verdict);
"""


class ATFDatabase:
    """Async-capable SQLite database for ATF state.

    Uses synchronous sqlite3 internally (suitable for local use).
    For true async at scale, swap this with an aiosqlite implementation.
    """

    def __init__(self, db_path: Path | str = ":memory:"):
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._conn

    # -- Passports ----------------------------------------------------------

    async def store_passport(self, passport_data: dict[str, Any]) -> None:
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO passports
               (passport_id, action_id, agent_id, tool_name, intent_hash,
                risk_score, simulation_risk, drift_score, policy_status,
                mirror_executed, mirror_matched, verdict, human_summary,
                signature, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                passport_data["passport_id"],
                passport_data["action_id"],
                passport_data["agent_id"],
                passport_data["tool_name"],
                passport_data["intent_hash"],
                passport_data["risk_score"],
                passport_data.get("simulation_risk"),
                passport_data.get("drift_score"),
                passport_data["policy_status"],
                int(passport_data.get("mirror_executed", False)),
                passport_data.get("mirror_matched"),
                passport_data["verdict"],
                passport_data.get("human_summary", ""),
                passport_data["signature"],
                passport_data["timestamp"],
            ),
        )
        conn.commit()

    async def get_passports(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
        min_risk: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        query = "SELECT * FROM passports WHERE 1=1"
        params: list[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if min_risk is not None:
            query += " AND risk_score >= ?"
            params.append(min_risk)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # -- Risk Assessments ---------------------------------------------------

    async def store_risk(self, action_id: str, assessment: dict[str, Any]) -> None:
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO risk_assessments
               (action_id, score, flags, requires_mirror, breakdown, computation_time_ms)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                action_id,
                assessment["score"],
                json.dumps(assessment.get("flags", [])),
                int(assessment.get("requires_mirror", False)),
                json.dumps(assessment.get("breakdown", {})),
                assessment.get("computation_time_ms", 0),
            ),
        )
        conn.commit()

    # -- Drift Embeddings ---------------------------------------------------

    async def store_drift_embedding(
        self,
        fingerprint: str,
        embedding: list[float],
        risk_score: float = 0.0,
        outcome: str = "unknown",
        is_failure: bool = False,
        agent_id: str = "",
    ) -> None:
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO drift_embeddings
               (action_fingerprint, embedding, risk_score, outcome, is_failure, agent_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fingerprint, json.dumps(embedding), risk_score, outcome, int(is_failure), agent_id),
        )
        conn.commit()

    async def get_drift_embeddings(
        self, failures_only: bool = False, limit: int = 1000
    ) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        query = "SELECT * FROM drift_embeddings"
        if failures_only:
            query += " WHERE is_failure = 1"
        query += " ORDER BY created_at DESC LIMIT ?"
        rows = conn.execute(query, (limit,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["embedding"] = json.loads(d["embedding"])
            results.append(d)
        return results

    async def store_drift_signature(
        self, name: str, embedding: list[float], failure_rate: float = 0.0
    ) -> None:
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO drift_signatures (signature_name, embedding, failure_rate)
               VALUES (?, ?, ?)""",
            (name, json.dumps(embedding), failure_rate),
        )
        conn.commit()

    async def get_drift_signatures(self) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        rows = conn.execute("SELECT * FROM drift_signatures").fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["embedding"] = json.loads(d["embedding"])
            results.append(d)
        return results

    # -- Pipeline Logs ------------------------------------------------------

    async def store_pipeline_log(self, log_data: dict[str, Any]) -> None:
        conn = self._ensure_conn()
        conn.execute(
            """INSERT INTO pipeline_logs
               (action_id, agent_id, tool_name, verdict, risk_score,
                pipeline_time_ms, full_result)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                log_data["action_id"],
                log_data["agent_id"],
                log_data["tool_name"],
                log_data["verdict"],
                log_data["risk_score"],
                log_data.get("pipeline_time_ms", 0),
                json.dumps(log_data.get("full_result", {})),
            ),
        )
        conn.commit()

    async def get_pipeline_logs(
        self, limit: int = 100, verdict: Optional[str] = None
    ) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        query = "SELECT * FROM pipeline_logs WHERE 1=1"
        params: list[Any] = []
        if verdict:
            query += " AND verdict = ?"
            params.append(verdict)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["full_result"] = json.loads(d["full_result"])
            results.append(d)
        return results

    async def get_stats(self) -> dict[str, Any]:
        """Dashboard statistics."""
        conn = self._ensure_conn()
        total = conn.execute("SELECT COUNT(*) FROM pipeline_logs").fetchone()[0]
        blocked = conn.execute(
            "SELECT COUNT(*) FROM pipeline_logs WHERE verdict = 'block'"
        ).fetchone()[0]
        avg_risk = conn.execute(
            "SELECT AVG(risk_score) FROM pipeline_logs"
        ).fetchone()[0]
        avg_time = conn.execute(
            "SELECT AVG(pipeline_time_ms) FROM pipeline_logs"
        ).fetchone()[0]
        return {
            "total_actions": total,
            "blocked_actions": blocked,
            "block_rate": blocked / total if total > 0 else 0,
            "average_risk_score": round(avg_risk or 0, 4),
            "average_pipeline_time_ms": round(avg_time or 0, 2),
        }
