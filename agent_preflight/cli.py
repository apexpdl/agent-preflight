"""CLI entry point for agent-preflight."""

import sys
import json


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

    print(f"Unknown command: {args[0]}")
    print(_help_text())
    sys.exit(1)


def _help_text():
    return """
agent-preflight - Preview AI agent actions before execution.

Usage:
    preflight demo       Run a demo showing preflight in action
    preflight version    Show version
    preflight help       Show this help

Python API:
    from agent_preflight import Preflight

    pf = Preflight()

    @pf.intercept
    def send_email(to, subject, body): ...

    plan = pf.dry_run(my_agent_fn, task="Send Q3 report")
    print(pf.format(plan))

    plan.approve()
    plan.execute()
"""


def _run_demo():
    """Run an interactive demo."""
    from . import Preflight

    pf = Preflight(cost_limit=1.00)

    # Define some fake agent tools
    @pf.intercept
    def search_contacts(query):
        return [{"name": "Sarah Chen", "email": "sarah@acme.com"}]

    @pf.intercept
    def send_email(to, subject, body):
        print(f"[SENT] Email to {to}: {subject}")

    @pf.intercept
    def update_database(query):
        print(f"[DB] Executed: {query}")

    @pf.intercept
    def delete_old_records(table, before_date):
        print(f"[DB] Deleted from {table} before {before_date}")

    @pf.intercept(cost=0.08, reversible=False)
    def generate_image(prompt, size="1024x1024"):
        print(f"[IMG] Generated: {prompt}")

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

    # Show JSON output too
    print("  JSON output available via plan.to_json()")
    print(f"  Plan has {len(plan.actions)} actions, risk: {plan.overall_risk.value}")
    print()


if __name__ == "__main__":
    main()
