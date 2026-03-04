"""
Audit trail persistence for agent-preflight.

Stores plan execution history for compliance, debugging, and analysis.
Supports JSON file storage and SQLite for production use.

Example:
    audit = AuditLog("./audit_trail")
    audit.record(plan, verdict="approved", actor="john@acme.com")

    # Query history
    recent = audit.query(last_n=10)
    critical = audit.query(risk_level=RiskLevel.CRITICAL)
    by_actor = audit.query(actor="john@acme.com")
"""

from __future__ import annotations

import json
import os
import time
import uuid
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import Plan, RiskLevel


@dataclass
class AuditEntry:
    """A single audit record."""
    id: str
    timestamp: float
    task: str
    action_count: int
    overall_risk: str
    total_cost: float
    irreversible_count: int
    warnings: list[str]
    verdict: str  # "approved", "denied", "auto-approved", etc.
    actor: str  # who approved/denied
    actions: list[dict]
    policy_result: Optional[dict] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "task": self.task,
            "action_count": self.action_count,
            "overall_risk": self.overall_risk,
            "total_cost": self.total_cost,
            "irreversible_count": self.irreversible_count,
            "warnings": self.warnings,
            "verdict": self.verdict,
            "actor": self.actor,
            "actions": self.actions,
            "policy_result": self.policy_result,
            "metadata": self.metadata,
        }


def _entry_from_plan(
    plan: Plan,
    verdict: str = "",
    actor: str = "",
    policy_result: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> AuditEntry:
    return AuditEntry(
        id=str(uuid.uuid4()),
        timestamp=time.time(),
        task=plan.task_description,
        action_count=len(plan.actions),
        overall_risk=plan.overall_risk.value,
        total_cost=plan.total_estimated_cost,
        irreversible_count=plan.irreversible_count,
        warnings=list(plan.warnings),
        verdict=verdict,
        actor=actor,
        actions=[a.to_dict() for a in plan.actions],
        policy_result=policy_result,
        metadata=metadata or {},
    )


class AuditLog:
    """
    Append-only audit log for preflight plans.

    Supports two backends:
    - JSON files (one file per entry, good for dev/small scale)
    - SQLite (single DB file, good for production/querying)
    """

    def __init__(self, path: str, backend: str = "json") -> None:
        """
        Args:
            path: Directory (json) or file path (sqlite) for storing audit data.
            backend: "json" or "sqlite".
        """
        self._path = Path(path)
        self._backend = backend

        if backend == "sqlite":
            self._init_sqlite()
        else:
            self._path.mkdir(parents=True, exist_ok=True)

    def _init_sqlite(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                task TEXT,
                action_count INTEGER,
                overall_risk TEXT,
                total_cost REAL,
                irreversible_count INTEGER,
                verdict TEXT,
                actor TEXT,
                data TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_risk ON audit_log(overall_risk)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_actor ON audit_log(actor)
        """)
        conn.commit()
        conn.close()

    def record(
        self,
        plan: Plan,
        verdict: str = "",
        actor: str = "",
        policy_result: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> AuditEntry:
        """Record a plan evaluation in the audit log."""
        entry = _entry_from_plan(plan, verdict, actor, policy_result, metadata)

        if self._backend == "sqlite":
            self._write_sqlite(entry)
        else:
            self._write_json(entry)

        return entry

    def _write_json(self, entry: AuditEntry) -> None:
        filename = f"{entry.id}.json"
        filepath = self._path / filename
        with open(filepath, "w") as f:
            json.dump(entry.to_dict(), f, indent=2, default=str)

    def _write_sqlite(self, entry: AuditEntry) -> None:
        conn = sqlite3.connect(str(self._path))
        conn.execute(
            """INSERT INTO audit_log
               (id, timestamp, task, action_count, overall_risk,
                total_cost, irreversible_count, verdict, actor, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.timestamp,
                entry.task,
                entry.action_count,
                entry.overall_risk,
                entry.total_cost,
                entry.irreversible_count,
                entry.verdict,
                entry.actor,
                json.dumps(entry.to_dict(), default=str),
            ),
        )
        conn.commit()
        conn.close()

    def query(
        self,
        last_n: Optional[int] = None,
        risk_level: Optional[RiskLevel] = None,
        actor: Optional[str] = None,
        verdict: Optional[str] = None,
        since: Optional[float] = None,
    ) -> list[AuditEntry]:
        """Query the audit log with optional filters."""
        if self._backend == "sqlite":
            return self._query_sqlite(last_n, risk_level, actor, verdict, since)
        return self._query_json(last_n, risk_level, actor, verdict, since)

    def _query_sqlite(self, last_n, risk_level, actor, verdict, since) -> list[AuditEntry]:
        conn = sqlite3.connect(str(self._path))
        query = "SELECT data FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if risk_level:
            query += " AND overall_risk = ?"
            params.append(risk_level.value)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
        if verdict:
            query += " AND verdict = ?"
            params.append(verdict)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp DESC"
        if last_n:
            query += f" LIMIT {last_n}"

        rows = conn.execute(query, params).fetchall()
        conn.close()

        entries = []
        for (data_json,) in rows:
            d = json.loads(data_json)
            entries.append(AuditEntry(**d))
        return entries

    def _query_json(self, last_n, risk_level, actor, verdict, since) -> list[AuditEntry]:
        entries = []
        if not self._path.exists():
            return entries

        for filepath in sorted(self._path.glob("*.json"), reverse=True):
            with open(filepath) as f:
                d = json.load(f)
            entry = AuditEntry(**d)

            if risk_level and entry.overall_risk != risk_level.value:
                continue
            if actor and entry.actor != actor:
                continue
            if verdict and entry.verdict != verdict:
                continue
            if since and entry.timestamp < since:
                continue

            entries.append(entry)
            if last_n and len(entries) >= last_n:
                break

        return entries

    def count(self) -> int:
        """Return total number of audit entries."""
        if self._backend == "sqlite":
            conn = sqlite3.connect(str(self._path))
            (n,) = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
            conn.close()
            return n
        return len(list(self._path.glob("*.json")))
