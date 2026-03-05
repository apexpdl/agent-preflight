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

    cmd = args[0]
    rest = args[1:]

    commands = {
        "version": _run_version,
        "demo": lambda a: _run_demo(),
        "check": _run_check,
        "audit": _run_audit,
        "enable": _run_enable,
        "serve": _run_serve,
        "dashboard": _run_dashboard,
        "atf": _run_atf_demo,
        "auto": _run_auto,
        "status": _run_status,
        "explain": _run_explain,
        "doctor": _run_doctor,
    }

    if cmd in commands:
        commands[cmd](rest)
    else:
        print(f"Unknown command: {cmd}")
        print(_help_text())
        sys.exit(1)


def _help_text():
    return """
  ▲ Preflight — Stop your AI agent before it destroys something.

  Usage:
    preflight demo                 Interactive demo with policy checks
    preflight atf                  Full ATF pipeline demo (screenshot-worthy)
    preflight status               Show Preflight status and session stats
    preflight explain <tool>       Explain why a tool would be flagged
    preflight doctor               Check your setup and diagnose issues
    preflight auto                 Auto-detect and enable for all frameworks
    preflight serve [--port N]     Start the ATF Gateway API server
    preflight dashboard [--port N] Start the monitoring dashboard
    preflight check <script>       Analyze a Python script's agent actions
    preflight audit [path]         View audit trail
    preflight enable --openclaw    Show OpenClaw integration guide
    preflight version              Show version
    preflight help                 Show this help

  Quick Start:
    from agent_preflight.integrations.openclaw import enable_preflight
    enable_preflight()  # done. every tool call is now safe.

  Zero-Config:
    PREFLIGHT_AUTO=1 python my_agent.py

  Modes: SAFE (default) | BALANCED | AGGRESSIVE | ENTERPRISE
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _run_version(args):
    from . import __version__
    from .display import render_startup_banner
    print(render_startup_banner(), end="")
    print(f"  Version: {__version__}")
    print()


def _run_status(args):
    """Show Preflight status: what's detected, what's active, session stats."""
    from .display import render_startup_banner, render_stats
    from .auto import detect_frameworks, status as auto_status

    print(render_startup_banner())

    # Detection
    frameworks = detect_frameworks()
    auto = auto_status()

    print("  Installed frameworks:")
    if frameworks:
        for f in frameworks:
            print(f"    ● {f}")
    else:
        print("    (none detected)")
    print()

    print("  Auto-detection:")
    if auto["enabled"]:
        print(f"    Active for: {', '.join(auto['detected_frameworks'])}")
    else:
        print("    Not active. Run: preflight auto")
    print()

    # Check env
    env_auto = os.environ.get("PREFLIGHT_AUTO", "")
    print("  Environment:")
    if env_auto in ("1", "true", "yes"):
        print("    PREFLIGHT_AUTO=1 (zero-config mode ON)")
    else:
        print("    PREFLIGHT_AUTO not set")
        print("    Set it for zero-config: export PREFLIGHT_AUTO=1")
    print()


def _run_explain(args):
    """Explain why a tool name would be flagged by the risk engine."""
    if not args:
        print("Usage: preflight explain <tool_name>")
        print("  Example: preflight explain delete_database_records")
        print("  Example: preflight explain get_user_profile")
        return

    import asyncio
    from .atf.risk_engine import RiskEngine
    from .atf.models import ActionEnvelope, StructuredIntent

    tool_name = args[0]

    # Build a test envelope
    envelope = ActionEnvelope(
        agent_id="explain-test",
        tool_name=tool_name,
        arguments={},
        intent=StructuredIntent(
            goal=f"Execute {tool_name}",
            reasoning_summary="Risk explanation test",
            confidence=0.7,
        ),
    )

    engine = RiskEngine()

    async def _assess():
        return await engine.assess(envelope)

    risk = asyncio.run(_assess())

    from .display import render_interception
    output = render_interception(
        tool_name=tool_name,
        verdict="block" if risk.score >= 0.6 else ("warn" if risk.score >= 0.3 else "allow"),
        risk_score=risk.score,
        flags=risk.flags,
        human_summary=f"Risk analysis for tool '{tool_name}'",
        pipeline_time_ms=risk.computation_time_ms,
    )
    print(output)

    if risk.breakdown:
        print("  Risk breakdown:")
        for feature, contribution in sorted(risk.breakdown.items(), key=lambda x: -x[1]):
            bar_len = int(contribution * 10)
            bar = "█" * bar_len
            print(f"    {feature:<25} +{contribution:.2f}  {bar}")
        print()

    if not risk.flags:
        print("  This tool name has no risk signals. It would pass silently.")
        print()


def _run_doctor(args):
    """Diagnose setup issues and verify everything is working."""
    from .display import render_startup_banner
    print(render_startup_banner())
    print("  Running diagnostics...\n")

    checks = []

    # Check 1: pydantic
    try:
        import pydantic
        checks.append(("Pydantic installed", True, f"v{pydantic.__version__}"))
    except ImportError:
        checks.append(("Pydantic installed", False, "pip install pydantic>=2.0"))

    # Check 2: ATF models
    try:
        from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
        checks.append(("ATF models loadable", True, ""))
    except Exception as e:
        checks.append(("ATF models loadable", False, str(e)))

    # Check 3: Risk engine
    try:
        import asyncio
        from agent_preflight.atf.risk_engine import RiskEngine
        from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
        engine = RiskEngine()
        envelope = ActionEnvelope(
            agent_id="test", tool_name="test_tool", arguments={},
            intent=StructuredIntent(goal="test", reasoning_summary="test"),
        )
        risk = asyncio.run(engine.assess(envelope))
        checks.append(("Risk engine working", True, f"test score: {risk.score:.4f}"))
    except Exception as e:
        checks.append(("Risk engine working", False, str(e)))

    # Check 4: Gateway
    try:
        from agent_preflight.atf.gateway import ATFGateway
        checks.append(("ATF Gateway importable", True, ""))
    except Exception as e:
        checks.append(("ATF Gateway importable", False, str(e)))

    # Check 5: FastAPI (optional)
    try:
        import fastapi
        checks.append(("FastAPI available", True, f"v{fastapi.__version__}"))
    except ImportError:
        checks.append(("FastAPI available", False, "pip install agent-preflight[server]"))

    # Check 6: Agent frameworks
    from agent_preflight.auto import detect_frameworks
    frameworks = detect_frameworks()
    if frameworks:
        checks.append(("Agent frameworks detected", True, ", ".join(frameworks)))
    else:
        checks.append(("Agent frameworks detected", False, "None found (install openclaw, langchain, etc.)"))

    # Check 7: Risk Memory
    try:
        from agent_preflight.atf.risk_memory import RiskMemory
        mem = RiskMemory()
        mem.record("test_tool", {}, 0.5, "allow", [], "test")
        recall = mem.recall("test_tool", {})
        checks.append(("Risk Memory working", True, ""))
    except Exception as e:
        checks.append(("Risk Memory working", False, str(e)))

    # Print results
    all_pass = True
    for name, passed, detail in checks:
        icon = "✓" if passed else "✗"
        color = "\033[92m" if passed else "\033[91m"
        reset = "\033[0m"
        line = f"  {color}{icon}{reset} {name}"
        if detail:
            line += f"  \033[2m{detail}\033[0m"
        print(line)
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  All checks passed. Preflight is ready.")
    else:
        print("  Some checks failed. Fix the issues above.")
    print()


def _run_demo():
    """Run an interactive demo with approval flow."""
    from . import Preflight
    from .policy import PolicyEngine, Policy
    from .models import RiskLevel, ActionType

    pf = Preflight(cost_limit=1.00)

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

    print("\n  Running agent in preflight mode...\n")
    plan = pf.dry_run(agent_workflow, task="Send Q3 report to Sarah at Acme")
    print(pf.format(plan))

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

    if plan.dependency_graph:
        print(f"  Dependency analysis:")
        print(f"    Execution order: {plan.dependency_graph.execution_order}")
        print(f"    Circular deps: {'YES' if plan.dependency_graph.has_cycles else 'No'}")
        print(f"    Critical path length: {len(plan.dependency_graph.critical_path)}")
    print()

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
        print()
        print("  ▲ Preflight for OpenClaw")
        print()
        print("  Option 1 — Zero config (recommended):")
        print("    PREFLIGHT_AUTO=1 python my_agent.py")
        print()
        print("  Option 2 — One line:")
        print("    from agent_preflight.integrations.openclaw import enable_preflight")
        print("    enable_preflight()")
        print()
        print("  Option 3 — Wrap a specific executor:")
        print("    pf = enable_preflight()")
        print("    safe_executor = pf.wrap_executor(your_executor)")
        print()
        print("  Option 4 — Import hook (zero code changes):")
        print("    import agent_preflight.hook  # auto-wraps OpenClaw on import")
        print()
        print("  Modes: SAFE | BALANCED | AGGRESSIVE | ENTERPRISE")
        print()
    else:
        print("Usage: preflight enable --openclaw")
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

    from .display import render_startup_banner
    print(render_startup_banner())
    print(f"  Gateway API starting on port {port} (mode: {mode})")
    print(f"  Docs:   http://localhost:{port}/docs")
    print(f"  Health: http://localhost:{port}/health")
    print()

    try:
        import uvicorn
        from agent_preflight.atf.config import ATFConfig, ExecutionMode
        from agent_preflight.atf.gateway import create_fastapi_app

        config = ATFConfig.for_mode(ExecutionMode(mode))
        app = create_fastapi_app(config)
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except ImportError:
        print("  Error: FastAPI and uvicorn required.")
        print("  Install: pip install agent-preflight[server]")
        sys.exit(1)


def _run_dashboard(args):
    """Start the ATF monitoring dashboard."""
    port = 8200
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    from .display import render_startup_banner
    print(render_startup_banner())
    print(f"  Dashboard starting on port {port}")
    print(f"  Open: http://localhost:{port}")
    print()

    try:
        import uvicorn
        from agent_preflight.dashboard.app import create_dashboard_app

        app = create_dashboard_app()
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except ImportError:
        print("  Error: FastAPI and uvicorn required.")
        print("  Install: pip install agent-preflight[server]")
        sys.exit(1)


def _run_atf_demo(args):
    """Run the ATF pipeline demo with screenshot-worthy output."""
    import asyncio

    async def demo():
        from agent_preflight.atf.gateway import ATFGateway
        from agent_preflight.atf.config import ATFConfig, ExecutionMode
        from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
        from agent_preflight.atf.plugins import ALL_PLUGINS
        from agent_preflight.display import render_interception, render_startup_banner

        config = ATFConfig.for_mode(ExecutionMode.SAFE, database_path=":memory:")
        gateway = ATFGateway(config)
        await gateway.initialize()
        gateway.register_plugins([p() for p in ALL_PLUGINS])

        print(render_startup_banner())

        scenarios = [
            {
                "label": "Safe read",
                "tool": "get_user_profile",
                "args": {"user_id": "12345"},
                "intent": StructuredIntent(
                    goal="Fetch user profile data",
                    reasoning_summary="Need to display user info",
                    irreversible=False, confidence=0.95,
                ),
            },
            {
                "label": "Production delete",
                "tool": "delete_database_records",
                "args": {"query": "DELETE FROM users WHERE active=false", "database": "prod"},
                "targets": ["/prod/database"],
                "intent": StructuredIntent(
                    goal="Clean up inactive users from production",
                    reasoning_summary="Remove users inactive for 1 year",
                    expected_state_changes=["users table row count decreases"],
                    irreversible=True, confidence=0.6,
                ),
            },
            {
                "label": "$50K wire transfer",
                "tool": "wire_transfer",
                "args": {"amount": 50000, "to": "external-account", "currency": "USD"},
                "intent": StructuredIntent(
                    goal="Transfer funds to vendor",
                    reasoning_summary="Quarterly payment",
                    expected_state_changes=["balance decreases by $50,000"],
                    external_calls=["banking-api.example.com"],
                    irreversible=True, estimated_cost=50000, confidence=0.85,
                ),
            },
        ]

        for scenario in scenarios:
            envelope = ActionEnvelope(
                agent_id="demo-agent",
                tool_name=scenario["tool"],
                arguments=scenario["args"],
                resource_targets=scenario.get("targets", []),
                intent=scenario["intent"],
            )

            result = await gateway.intercept_and_execute(envelope)

            sim_data = None
            if result.simulation_result:
                sim_data = {
                    "failure_probability": result.simulation_result.failure_probability,
                    "cascade_risk": result.simulation_result.cascade_probability,
                }

            correction_data = None
            if result.correction:
                correction_data = result.correction.model_dump()

            output = render_interception(
                tool_name=scenario["tool"],
                verdict=result.verdict.value,
                risk_score=result.risk_assessment.score,
                flags=result.risk_assessment.flags,
                human_summary=result.human_summary,
                correction=correction_data,
                pipeline_time_ms=result.total_pipeline_time_ms,
                passport_id=result.passport.passport_id if result.passport else "",
                simulation=sim_data,
            )
            print(output)

        # Stats
        stats = await gateway.db.get_stats()
        print(f"  Pipeline: {stats['total_actions']} evaluated, "
              f"{stats['blocked_actions']} blocked, "
              f"avg {stats['average_pipeline_time_ms']:.0f}ms")

        # Risk Memory stats
        mem_stats = gateway.risk_memory.get_stats()
        print(f"  Memory:   {mem_stats['total_patterns']} patterns learned, "
              f"{mem_stats['total_blocked']} blocks recorded")
        print()

    asyncio.run(demo())


def _run_auto(args):
    """Auto-detect and enable Preflight for all installed frameworks."""
    from .auto import enable, detect_frameworks
    from .display import render_startup_banner

    print(render_startup_banner())

    frameworks = detect_frameworks()
    if frameworks:
        print(f"  Detected: {', '.join(frameworks)}")
    else:
        print("  No supported agent frameworks detected.")
        print("  Supported: OpenClaw, LangChain, CrewAI, AutoGen, OpenAI, Anthropic")
        print()
        return

    wrapped = enable(verbose=False)
    if wrapped:
        print(f"  Enabled:  {', '.join(wrapped)}")
    else:
        print("  No frameworks could be auto-wrapped.")
        print("  Use: from agent_preflight.integrations.openclaw import enable_preflight")

    print()
    print("  For zero-config on every run:")
    print("    export PREFLIGHT_AUTO=1")
    print()


if __name__ == "__main__":
    main()
