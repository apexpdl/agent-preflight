"""Tests for TrustKernel rollback controller."""

import os
import tempfile
import pytest
from trust_kernel.rollback import RollbackController


class TestRollbackController:
    def setup_method(self):
        self.controller = RollbackController()

    def test_create_plan(self):
        plan = self.controller.create_plan("act-1")
        assert plan.action_id == "act-1"
        assert len(plan.entries) == 0

    def test_register_file_backup(self):
        entry = self.controller.register_file_backup(
            "act-1", "/tmp/target.txt", "/tmp/backup.txt"
        )
        assert entry.rollback_type == "file_restore"
        plan = self.controller.get_plan("act-1")
        assert len(plan.entries) == 1

    def test_register_db_rollback(self):
        entry = self.controller.register_db_rollback(
            "act-1", "users", "DELETE FROM users WHERE id = 42"
        )
        assert entry.rollback_type == "db_transaction"

    def test_register_api_compensator(self):
        called = []
        entry = self.controller.register_api_compensator(
            "act-1", "/api/undo", lambda: called.append(True)
        )
        assert entry.rollback_type == "api_compensate"

    def test_execute_rollback_api(self):
        called = []
        self.controller.register_api_compensator(
            "act-1", "/api/undo", lambda: called.append(True)
        )
        plan = self.controller.execute_rollback("act-1")
        assert len(called) == 1
        assert plan.coverage == 1.0

    def test_execute_rollback_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("original content")
            backup_path = f.name

        target_path = backup_path + ".target"
        with open(target_path, "w") as f:
            f.write("modified content")

        self.controller.register_file_backup("act-1", target_path, backup_path)
        plan = self.controller.execute_rollback("act-1")

        with open(target_path) as f:
            assert f.read() == "original content"

        os.unlink(backup_path)
        os.unlink(target_path)

    def test_execute_db_rollback(self):
        self.controller.register_db_rollback(
            "act-1", "users", "ROLLBACK"
        )
        plan = self.controller.execute_rollback("act-1")
        assert plan.entries[0].status == "completed"

    def test_rollback_nonexistent_returns_empty(self):
        plan = self.controller.execute_rollback("nonexistent")
        assert len(plan.entries) == 0

    def test_estimate_coverage(self):
        self.controller.register_db_rollback("act-1", "t1", "ROLLBACK")
        self.controller.register_db_rollback("act-1", "t2", "ROLLBACK")
        assert self.controller.estimate_coverage("act-1") == 1.0

    def test_clear(self):
        self.controller.register_db_rollback("act-1", "t1", "ROLLBACK")
        self.controller.clear()
        assert self.controller.get_plan("act-1") is None
