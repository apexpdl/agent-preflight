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

    print(f"Unknown command: {args[0]}")
    print(_help_text())
    sys.exit(1)


def _help_text():
    return """
agent-preflight - Preview AI agent actions before execution.

Usage:
    preflight demo            Run interactive demo with policy checks
    preflight check <script>  Analyze a Python script's agent actions
    preflight audit [path]    View audit trail
    preflight version         Show version
    preflight help            Show this help

Python API:
    from agent_preflight import Preflight

    pf = Preflight()

    @pf.intercept
    def send_email(to, subject, body): ...

    plan = pf.dry_run(my_agent_fn, task="Send Q3 report")
    print(pf.format(plan))

    plan.approve()
    plan.execute()

Policy Engine:
    from agent_preflight.policy import PolicyEngine, Policy

    engine = PolicyEngine()
    engine.add(Policy.deny("No drops").when_args_match(r"DROP TABLE"))
    result = engine.evaluate(plan)

Integrations:
    # OpenAI
    from agent_preflight.integrations.openai_hook import PreflightOpenAI

    # Anthropic
    from agent_preflight.integrations.anthropic_hook import PreflightAnthropic

    # LangChain
    from agent_preflight.integrations.langchain import PreflightCallbackHandler
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


if __name__ == "__main__":
    main()
