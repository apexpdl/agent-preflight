"""CLI entry point for agent-preflight."""

import sys
import json
import os


def main():
    """CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(_help_text())
        return

    if args[0] == "version":
        from . import __version__
        print(f"agent-preflight v{__version__}")
        return

    if args[0] == "demo":
        _run_demo()
        return

    if args[0] == "check":
        _run_check(args[1:])
        return

    if args[0] == "audit":
        _run_audit(args[1:])
        return

    if args[0] == "enable":
        _run_enable(args[1:])
        return

    if args[0] == "serve":
        _run_serve(args[1:])
        return

    if args[0] == "dashboard":
        _run_dashboard(args[1:])
        return

    if args[0] == "atf":
        _run_atf_demo(args[1:])
        return

    if args[0] == "auto":
        _run_auto(args[1:])
        return

    print(f"Unknown command: {args[0]}")
    print(_help_text())
    sys.exit(1)


def _help_text():
    return """
agent-preflight - Stop your AI agent before it destroys something.

Usage:
    preflight demo               Interactive demo with policy checks
    preflight atf                Full ATF pipeline demo
    preflight auto               Auto-detect and enable for all frameworks
    preflight serve [--port N]   Start the ATF Gateway API server
    preflight dashboard [--port N]  Start the monitoring dashboard
    preflight check <script>     Analyze a Python script's agent actions
    preflight audit [path]       View audit trail
    preflight enable --openclaw  Enable ATF governance for OpenClaw
    preflight version            Show version
    preflight help               Show this help

Quick Start (OpenClaw):
    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()  # done. every tool call is now safe.

Quick Start (Any Framework):
    from agent_preflight.auto import enable
    enable()  # auto-detects and wraps installed frameworks

Modes: SAFE (default) | BALANCED | AGGRESSIVE | ENTERPRISE
"""


def _run_demo():
    """Run an interactive demo with approval flow."""
    from . import Preflight
    from .policy import PolicyEngine, Policy
    from .models import RiskLevel, ActionType

    pf = Preflight(cost_limit=1.00)

    # Define some fake agent tools
    @pf.intercept
    def search_contacts(query):
        return [{"name": "Sarah Chen", "email": "sarah@acme.com"}]

    @pf.intercept
    def send_email(to, subject, body):
        print(f"  [SENT] Email to {to}: {subject}")

    @pf.intercept
    def update_database(query):
        print(f"  [DB] Executed: {query}")

    @pf.intercept
    def delete_old_records(table, before_date):
        print(f"  [DB] Deleted from {table} before {before_date}")

    @pf.intercept(cost=0.08, reversible=False)
    def generate_image(prompt, size="1024x1024"):
        print(f"  [IMG] Generated: {prompt}")

    # Simulate an agent workflow
    def agent_workflow():
        search_contacts("Sarah from Acme")
        send_email(
            to="sarah@acme.com",
            subject="Q3 Performance Report",
            body="Hi Sarah, please find the Q3 report attached...",
        )
        update_database("UPDATE invoices SET status='sent' WHERE quarter='Q3'")
        delete_old_records("temp_reports", before_date="2025-01-01")
        generate_image("Professional header image for Q3 report")

    # Run preflight
    print("\n  Running agent in preflight mode...\n")
    plan = pf.dry_run(agent_workflow, task="Send Q3 report to Sarah at Acme")

    # Display the plan
    print(pf.format(plan))

    # Run policy checks
    engine = PolicyEngine()
    engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
    engine.add(Policy.budget_limit("Budget cap", max_cost=5.0))

    result = engine.evaluate(plan)
    if result.violations:
        print(f"  Policy check: {len(result.violations)} finding(s)")
        for line in result.summary().split("\n"):
            print(f"  {line}")
    else:
        print("  Policy check: ALL CLEAR")
    print()

    # Show dependency graph
    if plan.dependency_graph:
        print(f"  Dependency analysis:")
        print(f"    Execution order: {plan.dependency_graph.execution_order}")
        print(f"    Circular deps: {'YES' if plan.dependency_graph.has_cycles else 'No'}")
        print(f"    Critical path length: {len(plan.dependency_graph.critical_path)}")
    print()

    # Interactive approval
    print("  Approve this plan? [y/N] ", end="", flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer in ("y", "yes"):
        plan.approve()
        print("\n  Plan APPROVED. Executing...\n")
        plan.execute()
        print("\n  Done!")
    else:
        print("\n  Plan REJECTED. No actions executed.")
    print()


def _run_check(args):
    """Analyze a Python script for agent actions."""
    if not args:
        print("Usage: preflight check <script.py>")
        print("  Runs a script and captures any preflight-intercepted actions.")
        sys.exit(1)

    script_path = args[0]
    if not os.path.exists(script_path):
        print(f"Error: File not found: {script_path}")
        sys.exit(1)

    print(f"\n  Analyzing: {script_path}")
    print(f"  (Script must use agent_preflight.Preflight and call pf.format())\n")

    import runpy
    try:
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit:
        pass
    except Exception as e:
        print(f"  Error running script: {e}")
        sys.exit(1)


def _run_audit(args):
    """View audit trail."""
    from .audit import AuditLog

    path = args[0] if args else "./preflight_audit"
    backend = "sqlite" if path.endswith(".db") else "json"

    if not os.path.exists(path):
        print(f"  No audit trail found at: {path}")
        print(f"  Create one with: AuditLog('{path}')")
        return

    audit = AuditLog(path, backend=backend)
    entries = audit.query(last_n=10)

    if not entries:
        print("  No audit entries found.")
        return

    print(f"\n  Last {len(entries)} audit entries from {path}:\n")
    for entry in entries:
        import datetime
        ts = datetime.datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M")
        risk_marker = "!!" if entry.overall_risk in ("HIGH", "CRITICAL") else "  "
        print(
            f"  {risk_marker} [{ts}] {entry.task or '(no task)'}"
            f"  risk={entry.overall_risk}"
            f"  actions={entry.action_count}"
            f"  verdict={entry.verdict or 'N/A'}"
        )
    print()


def _run_enable(args):
    """Enable ATF governance for agent frameworks."""
    if "--openclaw" in args:
        print("\n  Enabling Agent Preflight ATF for OpenClaw...\n")
        print("  Add this to your OpenClaw agent script:\n")
        print("    from agent_preflight.integrations.openclaw import enable_preflight")
        print("    pf = enable_preflight()")
        print("    safe_executor = pf.wrap_executor(your_tool_executor)")
        print()
        print("  Or for async agents:")
        print()
        print("    pf = enable_preflight()")
        print("    await pf.initialize()")
        print("    result = await pf.intercept('tool_name', {'arg': 'val'})")
        print()
        print("  Modes: SAFE | BALANCED | AGGRESSIVE | ENTERPRISE")
        print("    enable_preflight(mode=ExecutionMode.ENTERPRISE)")
        print()
    else:
        print("Usage: preflight enable --openclaw")
        print("  Prints integration instructions for OpenClaw agents.")
        sys.exit(1)


def _run_serve(args):
    """Start the ATF Gateway API server."""
    port = 8100
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    mode = "safe"
    for i, arg in enumerate(args):
        if arg == "--mode" and i + 1 < len(args):
            mode = args[i + 1]

    print(f"\n  Starting ATF Gateway on port {port} (mode: {mode})...")
    print(f"  API docs: http://localhost:{port}/docs")
    print(f"  Health: http://localhost:{port}/health\n")

    try:
        import uvicorn
        from agent_preflight.atf.config import ATFConfig, ExecutionMode
        from agent_preflight.atf.gateway import create_fastapi_app

        config = ATFConfig.for_mode(ExecutionMode(mode))
        app = create_fastapi_app(config)
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except ImportError:
        print("  Error: FastAPI and uvicorn required.")
        print("  Install with: pip install agent-preflight[server]")
        sys.exit(1)


def _run_dashboard(args):
    """Start the ATF monitoring dashboard."""
    port = 8200
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    print(f"\n  Starting ATF Dashboard on port {port}...")
    print(f"  Open: http://localhost:{port}\n")

    try:
        import uvicorn
        from agent_preflight.dashboard.app import create_dashboard_app

        app = create_dashboard_app()
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except ImportError:
        print("  Error: FastAPI and uvicorn required.")
        print("  Install with: pip install agent-preflight[server]")
        sys.exit(1)


def _run_atf_demo(args):
    """Run the ATF pipeline demo."""
    import asyncio

    async def demo():
        from agent_preflight.atf.gateway import ATFGateway
        from agent_preflight.atf.config import ATFConfig, ExecutionMode
        from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
        from agent_preflight.atf.plugins import ALL_PLUGINS

        config = ATFConfig.for_mode(ExecutionMode.SAFE, database_path=":memory:")
        gateway = ATFGateway(config)
        await gateway.initialize()
        gateway.register_plugins([p() for p in ALL_PLUGINS])

        print("\n  === ATF Pipeline Demo ===\n")

        # Low-risk action
        print("  [1] Low-risk action: read user profile")
        envelope1 = ActionEnvelope(
            agent_id="demo-agent",
            tool_name="get_user_profile",
            arguments={"user_id": "12345"},
            intent=StructuredIntent(
                goal="Fetch user profile data",
                reasoning_summary="Need to display user info",
                expected_state_changes=[],
                irreversible=False,
                estimated_cost=0.0,
                confidence=0.95,
            ),
        )
        r1 = await gateway.intercept_and_execute(envelope1)
        print(f"      Verdict: {r1.verdict.value}")
        print(f"      Risk: {r1.risk_assessment.score:.4f}")
        print(f"      Time: {r1.total_pipeline_time_ms:.0f}ms")
        print(f"      Summary: {r1.human_summary}")
        if r1.passport:
            print(f"      Passport: {r1.passport.passport_id[:16]}...")
        print()

        # High-risk action
        print("  [2] High-risk action: delete production database")
        envelope2 = ActionEnvelope(
            agent_id="demo-agent",
            tool_name="delete_database_records",
            arguments={"query": "DELETE FROM users WHERE active=false", "database": "prod"},
            resource_targets=["/prod/database"],
            intent=StructuredIntent(
                goal="Clean up inactive users from production database",
                reasoning_summary="Remove users who haven't logged in for 1 year",
                expected_state_changes=["users table row count decreases"],
                irreversible=True,
                estimated_cost=0.0,
                confidence=0.6,
            ),
        )
        r2 = await gateway.intercept_and_execute(envelope2)
        print(f"      Verdict: {r2.verdict.value}")
        print(f"      Risk: {r2.risk_assessment.score:.4f}")
        print(f"      Flags: {r2.risk_assessment.flags}")
        print(f"      Time: {r2.total_pipeline_time_ms:.0f}ms")
        print(f"      Summary: {r2.human_summary}")
        if r2.correction:
            print(f"      Correction feedback:")
            for s in r2.correction.suggestions[:3]:
                print(f"        - {s}")
        print()

        # Financial action
        print("  [3] Critical action: wire transfer")
        envelope3 = ActionEnvelope(
            agent_id="finance-bot",
            tool_name="wire_transfer",
            arguments={"amount": 50000, "to": "external-account", "currency": "USD"},
            intent=StructuredIntent(
                goal="Transfer funds to vendor",
                reasoning_summary="Quarterly payment to cloud provider",
                expected_state_changes=["account balance decreases by $50,000"],
                external_calls=["banking-api.example.com"],
                irreversible=True,
                estimated_cost=50000,
                confidence=0.85,
            ),
        )
        r3 = await gateway.intercept_and_execute(envelope3)
        print(f"      Verdict: {r3.verdict.value}")
        print(f"      Risk: {r3.risk_assessment.score:.4f}")
        print(f"      Flags: {r3.risk_assessment.flags}")
        print(f"      Time: {r3.total_pipeline_time_ms:.0f}ms")
        print(f"      Summary: {r3.human_summary}")
        print()

        # Stats
        stats = await gateway.db.get_stats()
        print("  === Pipeline Stats ===")
        print(f"      Total actions: {stats['total_actions']}")
        print(f"      Blocked: {stats['blocked_actions']}")
        print(f"      Block rate: {stats['block_rate']:.0%}")
        print(f"      Avg risk: {stats['average_risk_score']:.4f}")
        print(f"      Avg time: {stats['average_pipeline_time_ms']:.0f}ms")
        print()

    asyncio.run(demo())


def _run_auto(args):
    """Auto-detect and enable Preflight for all installed frameworks."""
    from .auto import enable, detect_frameworks

    print("\n  Agent Preflight — Auto-Detection\n")

    # Show what's installed
    frameworks = detect_frameworks()
    if frameworks:
        print(f"  Detected frameworks: {', '.join(frameworks)}")
    else:
        print("  No supported agent frameworks detected.")
        print("  Supported: OpenClaw, LangChain, CrewAI, AutoGen, OpenAI, Anthropic")
        print()
        return

    # Enable
    wrapped = enable(verbose=False)
    if wrapped:
        print(f"  Enabled Preflight for: {', '.join(wrapped)}")
    else:
        print("  No frameworks could be auto-wrapped.")
        print("  Use manual integration instead:")
        print()
        print("    from agent_preflight.integrations.openclaw import enable_preflight")
        print("    enable_preflight()")

    print()
    print("  To auto-enable on every run, set:")
    print("    export PREFLIGHT_AUTO=1")
    print()


if __name__ == "__main__":
    main()
