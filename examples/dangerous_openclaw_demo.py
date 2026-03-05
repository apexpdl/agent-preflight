"""
Dangerous OpenClaw Demo — Shows what Preflight catches.

Run this to see the difference between an unprotected agent
and one running with Preflight.

    python examples/dangerous_openclaw_demo.py
"""

import asyncio
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.config import ATFConfig, ExecutionMode
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
from agent_preflight.atf.plugins import ALL_PLUGINS
from agent_preflight.display import render_interception, render_startup_banner

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DANGEROUS_ACTIONS = [
    {
        "name": "delete_all_users",
        "desc": "Mass-delete production users",
        "tool": "delete_database_records",
        "args": {"query": "DELETE FROM users", "database": "production"},
        "targets": ["/prod/database"],
        "intent": StructuredIntent(
            goal="Delete all inactive users from production",
            reasoning_summary="Cleanup task",
            expected_state_changes=["users table emptied"],
            irreversible=True,
            confidence=0.4,
        ),
    },
    {
        "name": "rm_rf_slash",
        "desc": "Shell command: rm -rf /",
        "tool": "exec_shell",
        "args": {"command": "rm -rf /tmp/data/*", "sudo": True},
        "targets": [],
        "intent": StructuredIntent(
            goal="Clean up temporary data",
            reasoning_summary="Free disk space",
            expected_state_changes=["files deleted"],
            irreversible=True,
            confidence=0.5,
        ),
    },
    {
        "name": "wire_50k",
        "desc": "$50,000 wire transfer",
        "tool": "wire_transfer",
        "args": {"amount": 50000, "to": "unknown-external-account", "currency": "USD"},
        "targets": [],
        "intent": StructuredIntent(
            goal="Transfer $50K to vendor",
            reasoning_summary="Quarterly payment",
            expected_state_changes=["balance decreases by $50,000"],
            external_calls=["banking-api.example.com"],
            irreversible=True,
            estimated_cost=50000,
            confidence=0.7,
        ),
    },
    {
        "name": "mass_email",
        "desc": "Send 10,000 emails",
        "tool": "bulk_send_email",
        "args": {"template": "promo", "recipients": "all_users", "count": 10000},
        "targets": [],
        "intent": StructuredIntent(
            goal="Send promotional email to all users",
            reasoning_summary="Marketing campaign",
            expected_state_changes=["10,000 emails sent"],
            irreversible=True,
            confidence=0.6,
        ),
    },
    {
        "name": "safe_read",
        "desc": "Read user profile (safe)",
        "tool": "get_user_profile",
        "args": {"user_id": "12345"},
        "targets": [],
        "intent": StructuredIntent(
            goal="Fetch user profile for display",
            reasoning_summary="User requested their profile",
            irreversible=False,
            confidence=0.95,
        ),
    },
]


async def main():
    print()
    print("=" * 58)
    print("  DANGEROUS OPENCLAW DEMO")
    print("  What happens when your agent goes rogue?")
    print("=" * 58)

    # --- WITHOUT PREFLIGHT ---
    print()
    print("  WITHOUT PREFLIGHT:")
    print("  ─" * 29)
    for action in DANGEROUS_ACTIONS:
        status = "EXECUTED" if action["name"] != "safe_read" else "executed"
        danger = "💀" if action["name"] != "safe_read" else "✓ "
        print(f"    {danger} {action['tool']}() → {status}")
    print()
    print("  Result: $50K gone. Database wiped. 10K spam emails sent.")
    print("  Nobody saw it coming.")
    print()

    # --- WITH PREFLIGHT ---
    print("  WITH PREFLIGHT:")
    print("  ─" * 29)
    print(render_startup_banner())

    config = ATFConfig.for_mode(ExecutionMode.SAFE, database_path=":memory:")
    gateway = ATFGateway(config)
    await gateway.initialize()
    gateway.register_plugins([p() for p in ALL_PLUGINS])

    for action in DANGEROUS_ACTIONS:
        envelope = ActionEnvelope(
            agent_id="rogue-agent",
            tool_name=action["tool"],
            arguments=action["args"],
            resource_targets=action.get("targets", []),
            intent=action["intent"],
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
            tool_name=action["tool"],
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

    # Summary
    stats = await gateway.db.get_stats()
    print("  " + "=" * 56)
    print(f"  Total: {stats['total_actions']} actions evaluated")
    print(f"  Blocked: {stats['blocked_actions']} dangerous actions")
    print(f"  Allowed: {stats['total_actions'] - stats['blocked_actions']} safe actions")
    print(f"  Avg pipeline time: {stats['average_pipeline_time_ms']:.0f}ms")
    print("  " + "=" * 56)
    print()
    print("  Your agent ran. Nothing broke. That's Preflight.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
