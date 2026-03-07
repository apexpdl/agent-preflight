"""
TrustKernel — Enterprise AI Execution Layer Usage Example.

Demonstrates the full pipeline: intent declaration, risk assessment,
cryptographic signing, operator consensus, ledger recording, and
deterministic replay.
"""

import asyncio
from trust_kernel import (
    TrustKernel,
    CryptoProvider,
    ExecutionEnvelope,
)
from trust_kernel.kernel import TrustKernelConfig
from trust_kernel.models import (
    ActionType,
    CostBudget,
    MutabilityClass,
    StructuredIntent,
)


async def main():
    print("\n  === TrustKernel Enterprise Execution Demo ===\n")

    # Initialize with enterprise configuration
    config = TrustKernelConfig(
        db_path=":memory:",
        risk_threshold=0.7,
        required_approvals=1,
        budget=CostBudget(total_budget=10000.0, max_single_action=500.0),
        model_version="gpt-4o-2025-03",
    )
    kernel = TrustKernel(config)
    await kernel.initialize()

    # --- Example 1: Low-risk read operation ---
    print("  [1] Low-risk: Read user profile")
    env1 = ExecutionEnvelope(
        agent_id="data-agent",
        tool_name="get_user_profile",
        arguments={"user_id": "12345"},
        intent=StructuredIntent(
            goal="Fetch user profile for display",
            reasoning_summary="User requested their profile page",
            action_type=ActionType.READ,
            reversible=True,
            estimated_cost=0.01,
            confidence=0.98,
        ),
    )
    r1 = await kernel.execute(env1)
    print(f"      Verdict: {r1.verdict.value}")
    print(f"      Risk: {r1.dee.risk_score:.4f}")
    print(f"      Signatures: agent={r1.dee.agent_signature[:12]}...")
    print(f"      Pipeline: {r1.pipeline_time_ms:.1f}ms")
    print()

    # --- Example 2: High-risk destructive operation ---
    print("  [2] High-risk: Delete production records")
    env2 = ExecutionEnvelope(
        agent_id="cleanup-agent",
        tool_name="delete_inactive_users",
        arguments={"query": "DELETE FROM users WHERE last_login < '2024-01-01'"},
        resource_targets=["/prod/database/users"],
        intent=StructuredIntent(
            goal="Clean up inactive user accounts",
            reasoning_summary="Remove users inactive for over 1 year",
            action_type=ActionType.DELETE,
            target_resource="/prod/database/users",
            mutability_class=MutabilityClass.DESTRUCTIVE,
            reversible=False,
            estimated_cost=0.0,
            confidence=0.65,
            expected_state_changes=["users table row count decreases"],
        ),
    )
    r2 = await kernel.execute(env2, risk_score=0.85)
    print(f"      Verdict: {r2.verdict.value}")
    print(f"      Risk: {r2.dee.risk_score:.4f}")
    if r2.consensus_request_id:
        print(f"      Consensus Request: {r2.consensus_request_id}")
        # Simulate operator approval
        approved = await kernel.approve_consensus(
            r2.consensus_request_id, "admin-operator", "Reviewed and safe"
        )
        print(f"      Operator Approved: {approved}")
    print()

    # --- Example 3: Financial transaction ---
    print("  [3] Critical: Wire transfer")
    env3 = ExecutionEnvelope(
        agent_id="finance-bot",
        tool_name="wire_transfer",
        arguments={"amount": 50000, "to": "vendor-account", "currency": "USD"},
        intent=StructuredIntent(
            goal="Quarterly vendor payment",
            reasoning_summary="Scheduled payment to cloud provider",
            action_type=ActionType.API_CALL,
            reversible=False,
            estimated_cost=50000.0,
            confidence=0.9,
            external_calls=["banking-api.example.com"],
            expected_state_changes=["account balance decreased by $50,000"],
        ),
    )
    r3 = await kernel.execute(env3)
    print(f"      Verdict: {r3.verdict.value}")
    print(f"      Risk: {r3.dee.risk_score:.4f}")
    if r3.cost_alerts:
        for alert in r3.cost_alerts:
            print(f"      Cost Alert: [{alert.alert_type}] {alert.message}")
    print()

    # --- Verify ledger integrity ---
    print("  === Ledger Integrity Check ===")
    valid, count = await kernel.verify_ledger_integrity()
    print(f"      Chain valid: {valid}")
    print(f"      Verified records: {count}")
    print()

    # --- Stats ---
    stats = await kernel.get_ledger_stats()
    print("  === Execution Statistics ===")
    print(f"      Total actions: {stats['total_records']}")
    print(f"      Allowed: {stats['allowed']}")
    print(f"      Blocked: {stats['blocked']}")
    print(f"      Block rate: {stats['block_rate']:.0%}")
    print(f"      Budget spent: ${stats['cost_usage']['cost']['spent']:.2f}")
    print()

    # --- Reproducibility ---
    print("  === Reproducibility ===")
    manifest = kernel.reproducibility.export_manifest(env1.action_id)
    if manifest:
        print(f"      Manifest ID: {manifest['manifest_id'][:16]}...")
        print(f"      Manifest Hash: {manifest['manifest_hash'][:16]}...")
        print(f"      Model: {manifest['model_version']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
