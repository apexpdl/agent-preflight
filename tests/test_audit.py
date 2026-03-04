"""Tests for the audit trail."""

import sys, os, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_preflight import Preflight, RiskLevel
from agent_preflight.audit import AuditLog


def _make_plan(task="test task"):
    pf = Preflight()
    @pf.intercept
    def send_email(to, body): pass
    @pf.intercept
    def get_data(q): pass
    plan = pf.dry_run(lambda: (send_email("a@b.com", "hi"), get_data("users")), task=task)
    return plan


def test_json_audit_record():
    tmpdir = tempfile.mkdtemp()
    try:
        audit = AuditLog(tmpdir, backend="json")
        plan = _make_plan("json test")
        entry = audit.record(plan, verdict="approved", actor="test@acme.com")
        assert entry.id
        assert entry.task == "json test"
        assert entry.verdict == "approved"
        assert entry.action_count == 2
        assert audit.count() == 1
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: json_audit_record")


def test_json_audit_query():
    tmpdir = tempfile.mkdtemp()
    try:
        audit = AuditLog(tmpdir, backend="json")
        for i in range(5):
            plan = _make_plan(f"task {i}")
            audit.record(plan, verdict="approved" if i % 2 == 0 else "denied", actor="user")

        all_entries = audit.query()
        assert len(all_entries) == 5

        last_2 = audit.query(last_n=2)
        assert len(last_2) == 2

        approved = audit.query(verdict="approved")
        assert len(approved) == 3
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: json_audit_query")


def test_sqlite_audit_record():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "audit.db")
    try:
        audit = AuditLog(db_path, backend="sqlite")
        plan = _make_plan("sqlite test")
        entry = audit.record(plan, verdict="denied", actor="admin")
        assert entry.id
        assert audit.count() == 1
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: sqlite_audit_record")


def test_sqlite_audit_query():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "audit.db")
    try:
        audit = AuditLog(db_path, backend="sqlite")
        for i in range(5):
            plan = _make_plan(f"task {i}")
            audit.record(plan, verdict="approved", actor=f"user{i}")

        all_entries = audit.query()
        assert len(all_entries) == 5

        last_3 = audit.query(last_n=3)
        assert len(last_3) == 3

        by_actor = audit.query(actor="user2")
        assert len(by_actor) == 1
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: sqlite_audit_query")


def test_audit_entry_to_dict():
    tmpdir = tempfile.mkdtemp()
    try:
        audit = AuditLog(tmpdir, backend="json")
        plan = _make_plan("dict test")
        entry = audit.record(plan, verdict="approved", actor="bot",
                             metadata={"run_id": "abc123"})
        d = entry.to_dict()
        assert d["verdict"] == "approved"
        assert d["actor"] == "bot"
        assert d["metadata"]["run_id"] == "abc123"
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: audit_entry_to_dict")


def test_audit_with_policy_result():
    tmpdir = tempfile.mkdtemp()
    try:
        audit = AuditLog(tmpdir, backend="json")
        plan = _make_plan("policy test")
        policy_data = {"blocked": False, "passed": 3, "violations": []}
        entry = audit.record(plan, verdict="auto-approved",
                             policy_result=policy_data)
        assert entry.policy_result == policy_data
    finally:
        shutil.rmtree(tmpdir)
    print("PASS: audit_with_policy_result")


if __name__ == "__main__":
    test_json_audit_record()
    test_json_audit_query()
    test_sqlite_audit_record()
    test_sqlite_audit_query()
    test_audit_entry_to_dict()
    test_audit_with_policy_result()
    print()
    print("All 6 audit tests passed!")
