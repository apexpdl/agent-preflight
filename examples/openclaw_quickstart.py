"""
OpenClaw + Preflight — Quickstart Example

Shows how easy it is to add safety to any OpenClaw agent.
Three options from easiest to most customizable.
"""

# ============================================================
# OPTION 1: Zero config (easiest)
# ============================================================
# Just import and enable. That's it.

from agent_preflight.integrations.openclaw import enable_preflight

pf = enable_preflight()

# Now ALL your OpenClaw tool calls go through Preflight automatically.
# Low-risk actions execute silently. High-risk actions get blocked.

# ============================================================
# OPTION 2: Wrap a specific executor
# ============================================================

def my_tool_executor(tool_name, arguments):
    """Your existing tool executor."""
    print(f"Executing {tool_name} with {arguments}")
    return {"status": "ok"}

# Wrap it — now it's safe
safe_executor = pf.wrap_sync_executor(my_tool_executor)

# Safe action — passes silently
result = safe_executor("get_user_profile", {"user_id": "12345"})
print(f"Safe action: {result}")

# Dangerous action — gets blocked
result = safe_executor("delete_database", {"table": "users", "confirm": True})
print(f"Dangerous action: {result}")

# ============================================================
# OPTION 3: Wrap individual tool functions
# ============================================================

@pf.wrap_tool
def send_email(to, subject, body):
    """Send an email — Preflight checks risk before executing."""
    print(f"Sending email to {to}: {subject}")

@pf.wrap_tool
def read_file(path):
    """Read a file — low risk, passes silently."""
    print(f"Reading {path}")

# ============================================================
# OPTION 4: Full async integration
# ============================================================

import asyncio

async def async_demo():
    """Full async integration with the ATF pipeline."""
    # Intercept a single action
    result = await pf.intercept(
        tool_name="wire_transfer",
        arguments={"amount": 50000, "to": "external-account"},
        agent_id="finance-bot",
        intent_goal="Transfer funds to vendor",
    )
    print(f"\nWire transfer verdict: {result['verdict']}")
    print(f"Risk score: {result['risk_score']:.2%}")
    if result.get("correction"):
        print(f"Suggestion: {result['correction']['suggestions'][0]}")

    # Check stats
    print(f"\nPreflight stats: {pf.stats}")

if __name__ == "__main__":
    asyncio.run(async_demo())
