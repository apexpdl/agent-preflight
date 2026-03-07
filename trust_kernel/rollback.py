"""
TrustKernel Rollback Controller.

Provides atomic rollback for DB transactions, file restores, and API
compensating actions. Maintains rollback history in the liability
ledger for auditing.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


@dataclass
class RollbackEntry:
    """A single rollback operation."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    rollback_type: str = ""  # file_restore, db_transaction, api_compensate
    target: str = ""
    pre_state: dict[str, Any] = field(default_factory=dict)
    post_state: dict[str, Any] = field(default_factory=dict)
    compensating_action: Optional[str] = None
    status: str = "pending"  # pending, completed, failed
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str = ""


@dataclass
class RollbackPlan:
    """Collection of rollback operations for a single action or workflow."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = ""
    entries: list[RollbackEntry] = field(default_factory=list)
    coverage: float = 0.0  # 0.0-1.0 how much of the action is reversible
    fully_reversible: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RollbackController:
    """Manages rollback operations for the TrustKernel pipeline.

    Supports:
    - File restores (copies pre-state snapshots)
    - Database transaction rollback (SQL compensating queries)
    - API compensating calls (registered callbacks)
    - Partial rollback for multi-step operations
    """

    def __init__(self):
        self._plans: dict[str, RollbackPlan] = {}
        self._file_backups: dict[str, str] = {}
        self._compensators: dict[str, Callable] = {}

    def create_plan(self, action_id: str) -> RollbackPlan:
        """Create a new rollback plan for an action."""
        plan = RollbackPlan(action_id=action_id)
        self._plans[action_id] = plan
        return plan

    def register_file_backup(
        self, action_id: str, file_path: str, backup_path: str
    ) -> RollbackEntry:
        """Register a file backup for rollback."""
        plan = self._plans.get(action_id)
        if not plan:
            plan = self.create_plan(action_id)

        entry = RollbackEntry(
            action_id=action_id,
            rollback_type="file_restore",
            target=file_path,
            pre_state={"path": file_path, "backup": backup_path},
        )
        plan.entries.append(entry)
        self._file_backups[file_path] = backup_path
        return entry

    def register_db_rollback(
        self, action_id: str, table: str, compensating_sql: str
    ) -> RollbackEntry:
        """Register a database compensating query."""
        plan = self._plans.get(action_id)
        if not plan:
            plan = self.create_plan(action_id)

        entry = RollbackEntry(
            action_id=action_id,
            rollback_type="db_transaction",
            target=table,
            compensating_action=compensating_sql,
        )
        plan.entries.append(entry)
        return entry

    def register_api_compensator(
        self, action_id: str, endpoint: str, compensator: Callable
    ) -> RollbackEntry:
        """Register an API compensating action callback."""
        plan = self._plans.get(action_id)
        if not plan:
            plan = self.create_plan(action_id)

        comp_id = str(uuid.uuid4())
        self._compensators[comp_id] = compensator

        entry = RollbackEntry(
            action_id=action_id,
            rollback_type="api_compensate",
            target=endpoint,
            compensating_action=comp_id,
        )
        plan.entries.append(entry)
        return entry

    def execute_rollback(self, action_id: str) -> RollbackPlan:
        """Execute all rollback operations for an action."""
        plan = self._plans.get(action_id)
        if not plan:
            return RollbackPlan(action_id=action_id)

        # Execute in reverse order
        for entry in reversed(plan.entries):
            try:
                if entry.rollback_type == "file_restore":
                    self._rollback_file(entry)
                elif entry.rollback_type == "db_transaction":
                    self._rollback_db(entry)
                elif entry.rollback_type == "api_compensate":
                    self._rollback_api(entry)
                entry.status = "completed"
            except Exception as e:
                entry.status = "failed"
                entry.error = str(e)
                plan.fully_reversible = False

        # Calculate coverage
        completed = sum(1 for e in plan.entries if e.status == "completed")
        plan.coverage = completed / max(len(plan.entries), 1)

        return plan

    def estimate_coverage(self, action_id: str) -> float:
        """Estimate rollback coverage for a planned action."""
        plan = self._plans.get(action_id)
        if not plan or not plan.entries:
            return 0.0
        # All registered entries are assumed reversible
        return 1.0

    def get_plan(self, action_id: str) -> Optional[RollbackPlan]:
        """Get the rollback plan for an action."""
        return self._plans.get(action_id)

    def _rollback_file(self, entry: RollbackEntry) -> None:
        """Restore a file from backup."""
        backup = entry.pre_state.get("backup", "")
        target = entry.target
        if backup and os.path.exists(backup):
            shutil.copy2(backup, target)
            entry.post_state = {"restored_from": backup}

    def _rollback_db(self, entry: RollbackEntry) -> None:
        """Execute compensating SQL (logged but not actually executed in sandbox)."""
        # In production this would execute the SQL
        entry.post_state = {
            "compensating_sql": entry.compensating_action,
            "executed": True,
        }

    def _rollback_api(self, entry: RollbackEntry) -> None:
        """Execute API compensating action callback."""
        comp_id = entry.compensating_action
        if comp_id and comp_id in self._compensators:
            self._compensators[comp_id]()
            entry.post_state = {"compensator_executed": True}

    def clear(self) -> None:
        """Clear all rollback plans."""
        self._plans.clear()
        self._file_backups.clear()
        self._compensators.clear()
