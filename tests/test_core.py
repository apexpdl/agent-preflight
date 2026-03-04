import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_preflight import Preflight, RiskLevel, Reversibility, ActionType


def test_basic_capture():
    pf = Preflight()
    @pf.intercept
    def my_func(x, y): return x + y
    plan = pf.dry_run(lambda: my_func(1, 2))
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "my_func"
    assert plan.actions[0].args == {"x": 1, "y": 2}
    print("PASS: basic_capture")


def test_no_execution():
    pf = Preflight()
    executed = []
    @pf.intercept
    def boom(msg): executed.append(msg)
    plan = pf.dry_run(lambda: boom("fire"))
    assert len(executed) == 0
    print("PASS: no_execution_in_dry_run")


def test_approve_required():
    pf = Preflight()
    @pf.intercept
    def noop(): pass
    plan = pf.dry_run(lambda: noop())
    try:
        plan.execute()
        assert False
    except RuntimeError:
        pass
    plan.approve()
    plan.execute()
    print("PASS: approve_required")


def test_email_irreversible():
    pf = Preflight()
    @pf.intercept
    def send_email(to, body): pass
    plan = pf.dry_run(lambda: send_email("a@b.com", "hi"))
    a = plan.actions[0]
    assert a.reversibility == Reversibility.IRREVERSIBLE
    assert a.risk_level == RiskLevel.HIGH
    print("PASS: email_irreversible")


def test_read_low_risk():
    pf = Preflight()
    @pf.intercept
    def get_users(q): pass
    plan = pf.dry_run(lambda: get_users("active"))
    a = plan.actions[0]
    assert a.action_type == ActionType.READ
    assert a.risk_level == RiskLevel.LOW
    print("PASS: read_low_risk")


def test_sql_detection():
    pf = Preflight()
    @pf.intercept
    def run_query(sql): pass
    plan = pf.dry_run(lambda: run_query("DROP TABLE users"))
    a = plan.actions[0]
    assert a.risk_level == RiskLevel.CRITICAL
    assert any("SQL" in r or "Dangerous" in r for r in a.risk_reasons)
    print("PASS: sql_detection")


def test_loop_detection():
    pf = Preflight()
    @pf.intercept
    def api_call(ep): pass
    def loopy():
        for _ in range(5): api_call("/data")
    plan = pf.dry_run(loopy)
    assert any("LOOP" in w for w in plan.warnings)
    assert plan.overall_risk == RiskLevel.CRITICAL
    print("PASS: loop_detection")


def test_cost_limit():
    pf = Preflight(cost_limit=0.01)
    @pf.intercept(cost=0.05)
    def expensive(): pass
    plan = pf.dry_run(lambda: expensive())
    assert any("COST LIMIT" in w for w in plan.warnings)
    print("PASS: cost_limit")


def test_json_export():
    import json
    pf = Preflight()
    @pf.intercept
    def fetch_data(url): pass
    plan = pf.dry_run(lambda: fetch_data("https://api.example.com"))
    data = json.loads(plan.to_json())
    assert "actions" in data
    assert data["summary"]["total_actions"] == 1
    print("PASS: json_export")


def test_context_manager():
    pf = Preflight()
    @pf.intercept
    def do_thing(x): pass
    with pf.recording(task="test") as rec:
        do_thing(42)
        do_thing(99)
    assert rec.plan is not None
    assert len(rec.plan.actions) == 2
    print("PASS: context_manager")


def test_plain_render():
    pf = Preflight()
    @pf.intercept
    def delete_user(uid): pass
    plan = pf.dry_run(lambda: delete_user(123))
    out = pf.format(plan, color=False)
    assert "PREFLIGHT PLAN" in out
    assert "delete_user" in out
    print("PASS: plain_render")


def test_async_intercept():
    pf = Preflight()
    @pf.intercept
    async def async_fetch(url): return "data"

    async def workflow():
        await async_fetch("https://api.example.com")

    plan = asyncio.get_event_loop().run_until_complete(
        pf.async_dry_run(workflow, task="async test")
    )
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "async_fetch"
    print("PASS: async_intercept")


def test_async_recording():
    pf = Preflight()
    @pf.intercept
    async def async_op(x): pass

    async def run():
        async with pf.async_recording(task="async rec") as rec:
            await async_op(1)
            await async_op(2)
        return rec

    rec = asyncio.get_event_loop().run_until_complete(run())
    assert rec.plan is not None
    assert len(rec.plan.actions) == 2
    print("PASS: async_recording")


def test_dependency_graph():
    pf = Preflight()
    @pf.intercept
    def read_data(source): pass
    @pf.intercept
    def write_data(dest, content): pass
    @pf.intercept
    def delete_data(target): pass

    def workflow():
        read_data("users_table")
        write_data("backup_table", "content")
        delete_data("users_table")

    plan = pf.dry_run(workflow, task="migrate data")
    assert plan.dependency_graph is not None
    assert not plan.dependency_graph.has_cycles
    assert len(plan.dependency_graph.execution_order) == 3
    print("PASS: dependency_graph")


def test_delete_without_read_warning():
    pf = Preflight()
    @pf.intercept
    def delete_records(table): pass

    plan = pf.dry_run(lambda: delete_records("important_data"), task="cleanup")
    assert any("blind delete" in w.lower() or "without prior READ" in w for w in plan.warnings)
    print("PASS: delete_without_read_warning")


def test_dependency_json_export():
    import json
    pf = Preflight()
    @pf.intercept
    def step_a(x): pass
    @pf.intercept
    def step_b(x): pass

    def workflow():
        step_a("input")
        step_b("input")

    plan = pf.dry_run(workflow, task="pipeline")
    data = json.loads(plan.to_json())
    assert "dependencies" in data
    assert "execution_order" in data["dependencies"]
    print("PASS: dependency_json_export")


if __name__ == "__main__":
    test_basic_capture()
    test_no_execution()
    test_approve_required()
    test_email_irreversible()
    test_read_low_risk()
    test_sql_detection()
    test_loop_detection()
    test_cost_limit()
    test_json_export()
    test_context_manager()
    test_plain_render()
    test_async_intercept()
    test_async_recording()
    test_dependency_graph()
    test_delete_without_read_warning()
    test_dependency_json_export()
    print()
    print("All 16 tests passed!")
