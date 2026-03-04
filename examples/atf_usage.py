"""
Agent Preflight ATF — Usage Examples

Demonstrates the full Autonomous Trust Fabric pipeline:
risk scoring, simulation, drift detection, policy enforcement,
mirror world sandbox, and signed action passports.
"""

import asyncio
from agent_preflight.atf.gateway import ATFGateway
from agent_preflight.atf.config import ATFConfig, ExecutionMode
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent
from agent_preflight.atf.plugins import ALL_PLUGINS
from agent_preflight.atf.policy_v2 import PolicyRule


async def main():
    # 1. Initialize the ATF Gateway
    config = ATFConfig.for_mode(ExecutionMode.SAFE, database_path=":memory:")
    gateway = ATFGateway(config)
    await gateway.initialize()
    gateway.register_plugins([p() for p in ALL_PLUGINS])

    # 2. Add custom policies
    gateway.policy_engine.add_rule(
        PolicyRule("no_prod_delete", 'path startswith "/prod" AND tool matches "delete"', "block")
    )
    gateway.policy_engine.add_rule(
        PolicyRule("cost_approval", "estimated_cost > 100", "require_approval")
    )

    # 3. Safe action — gets approved with passport
    safe_action = ActionEnvelope(
        agent_id="my-agent",
        tool_name="fetch_user_profile",
        arguments={"user_id": "u_12345"},
        intent=StructuredIntent(
            goal="Retrieve user profile for display",
            reasoning_summary="User requested their profile page",
            confidence=0.95,
        ),
    )
    result = await gateway.intercept_and_execute(safe_action)
    print(f"Safe action verdict: {result.verdict.value}")
    print(f"Risk score: {result.risk_assessment.score:.2%}")
    print(f"Passport ID: {result.passport.passport_id[:16]}...")
    print(f"Summary: {result.human_summary}")
    print()

    # 4. Dangerous action — gets blocked
    dangerous_action = ActionEnvelope(
        agent_id="rogue-agent",
        tool_name="delete_all_records",
        arguments={"table": "users", "confirm": True},
        resource_targets=["/prod/database"],
        intent=StructuredIntent(
            goal="Delete all user records",
            reasoning_summary="Data cleanup request",
            irreversible=True,
            estimated_cost=0,
            confidence=0.3,
        ),
    )
    result = await gateway.intercept_and_execute(dangerous_action)
    print(f"Dangerous action verdict: {result.verdict.value}")
    print(f"Risk score: {result.risk_assessment.score:.2%}")
    print(f"Flags: {result.risk_assessment.flags}")
    if result.correction:
        print(f"Correction suggestions:")
        for s in result.correction.suggestions:
            print(f"  - {s}")
    print()

    # 5. View pipeline stats
    stats = await gateway.db.get_stats()
    print(f"Pipeline stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
