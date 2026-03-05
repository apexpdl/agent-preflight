# Agent Preflight

**Stop your AI agent before it destroys something.**

One line of code. Zero config. Your agent's actions are risk-scored, simulated, and blocked before they touch the real world.

```
pip install agent-preflight
```

```python
from agent_preflight.integrations.openclaw import enable_preflight

enable_preflight()  # done. every tool call is now safe.
```

That's it. No architecture diagrams. No config files. No PhD required.

---

## What happens under the hood

Every time your agent tries to do something — send an email, delete a record, make an API call — Preflight intercepts it and asks one question: **"Is this safe?"**

```
Your agent wants to: delete_database_records(table="users", env="prod")

Preflight says:
  Risk:     99.8%
  Verdict:  BLOCKED
  Flags:    [irreversible, destructive_tool, sensitive_path]
  Why:      "Deleting production database records is irreversible.
             Try reading first, then deleting with a WHERE clause."
```

Low-risk actions (reading files, fetching profiles) pass through **silently**. No popups. No interruptions. Your agent runs at full speed.

High-risk actions (deleting data, sending money, running shell commands) get **blocked with suggestions** for safer alternatives.

You only see Preflight when it matters.

---

## Why this exists

Real incidents. Real money lost.

- **$47K** burned by a recursive agent loop running 11 days unnoticed
- **Production databases** deleted by coding agents despite freeze instructions
- **$2.3M** in fraudulent wire transfers approved by AI assistants
- **1,184 malicious agent skills** found on package registries

Every incident had the same root cause: **nobody saw what the agent was about to do.**

Observability tools watch *after*. Security tools *block everything*. Preflight **shows you the plan and only blocks what's actually dangerous.**

---

## Works with everything

### OpenClaw (1 line)

```python
from agent_preflight.integrations.openclaw import enable_preflight
enable_preflight()
# all OpenClaw tool calls are now governed
```

### OpenAI function calling

```python
from agent_preflight.integrations.openai_hook import PreflightOpenAI

pf = Preflight()
hook = PreflightOpenAI(pf)
hook.register_tool("send_email", send_email_fn)
hook.capture_from_response(response)
plan = hook.build_plan(task="Send report")
```

### Anthropic tool use

```python
from agent_preflight.integrations.anthropic_hook import PreflightAnthropic

pf = Preflight()
hook = PreflightAnthropic(pf)
hook.register_tool("search_db", search_db_fn)
hook.capture_from_response(response)
plan = hook.build_plan(task="Search users")
```

### LangChain / LangGraph

```python
from agent_preflight.integrations.langchain import PreflightCallbackHandler

handler = PreflightCallbackHandler(Preflight())
agent.invoke({"input": "Organize tasks"}, config={"callbacks": [handler.handler]})
plan = handler.build_plan(task="Organize tasks")
```

### Any Python agent

```python
from agent_preflight import Preflight

pf = Preflight()

@pf.intercept
def send_email(to, subject, body):
    smtp.send(to, subject, body)

@pf.intercept
def delete_records(table, condition):
    db.execute(f"DELETE FROM {table} WHERE {condition}")

plan = pf.dry_run(my_workflow, task="Clean up old data")
print(pf.format(plan))  # see everything before it runs
plan.approve()
plan.execute()
```

### Zero config auto-detect

```python
# Detects installed frameworks and wraps them automatically
from agent_preflight.auto import enable
enable()  # wraps OpenClaw, LangChain, CrewAI, AutoGen — whatever's installed
```

Or set an environment variable:
```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

---

## The full pipeline (for the technically curious)

When Preflight intercepts an action, it runs through 6 stages in under 5ms for low-risk actions:

```
Agent action
    |
    v
1. INTENT COMPILER -----> Validates what the agent says it's doing
    |
    v
2. RISK ENGINE (<1ms) --> Weighted scoring: destructive? irreversible? financial?
    |                      shell execution? sensitive paths? low confidence?
    v
3. SIMULATION ENGINE ---> Monte Carlo: 50-200 rollouts simulating failure scenarios
    |                      "What if network is slow? Memory is low? Load is high?"
    v
4. DRIFT INTELLIGENCE --> "Have we seen similar actions fail before?"
    |                      Anomaly detection against historical patterns
    v
5. POLICY ENGINE -------> YAML rules: "No prod deletes", "Max $500 spend"
    |
    v
6. MIRROR WORLD --------> Runs action in sandbox, compares result to declared intent
    |
    v
VERDICT: ALLOW / WARN / BLOCK
    |
    +-- If ALLOWED: Issues signed Action Passport (HMAC-SHA256, tamper-proof)
    +-- If BLOCKED: Returns correction with safer alternatives
```

### Risk scoring

Pure computation, no LLM calls. Runs in under 1ms.

| Signal | Weight | Example |
|--------|--------|---------|
| Irreversible action | 3.0x | `send_email`, `wire_transfer` |
| Destructive tool | 2.5x | `delete`, `drop`, `truncate`, `rm` |
| Financial operation | 2.8x | `pay`, `transfer`, `charge`, `wire` |
| Shell execution | 2.2x | `exec`, `bash`, `system`, `eval` |
| Sensitive path | 2.0x | `.env`, `/etc/`, `prod`, `credentials` |
| High cost | 1.8x | Estimated cost > $100 |
| Low confidence | 1.5x | Agent confidence < 50% |
| Drift similarity | 2.0x | Similar to past failures |

Score = sigmoid(weighted_sum + bias) -> 0.0 to 1.0

### Monte Carlo simulation

Runs 50-200 simulated scenarios with random perturbations:
- Filesystem cascades (deleting a file that other files depend on)
- API cost explosions (retry loops that multiply costs)
- Dependency breaks (removing packages other services need)
- Memory runaway (operations that eat all available RAM)
- Infrastructure mutations (changing configs that affect other services)

Returns failure probability, cascade risk, and volatility index.

### Action Passports

Every allowed action gets a signed, tamper-proof audit artifact:

```json
{
  "passport_id": "a1b2c3d4...",
  "agent_id": "my-agent",
  "tool_name": "update_database",
  "risk_score": 0.12,
  "verdict": "allow",
  "signature": "hmac-sha256:e4f5a6b7..."
}
```

Verifiable. Auditable. Compliance-ready.

---

## Smart interruptions

Preflight doesn't ask "are you sure?" for everything. That's annoying and useless.

| Risk level | What happens | Example |
|-----------|-------------|---------|
| **Low** (0-30%) | Passes silently | `get_user()`, `read_file()`, `search()` |
| **Medium** (30-60%) | Warning + allows | `update_database()`, `send_notification()` |
| **High** (60-80%) | Blocks + suggests alternative | `delete_records()`, `exec_shell()` |
| **Critical** (80%+) | Hard block + correction | `drop_table()`, `wire_transfer()` |

If the **user** explicitly asked the agent to do something, Preflight gives it more trust. If the **agent** decided to do it autonomously, Preflight is more cautious.

---

## CLI

```bash
preflight demo                    # interactive demo
preflight atf                     # full ATF pipeline demo
preflight serve --port 8100       # start REST API server
preflight dashboard --port 8200   # start monitoring dashboard
preflight check script.py         # analyze a script's agent actions
preflight audit ./trail           # view audit history
preflight enable --openclaw       # show OpenClaw integration guide
preflight auto                    # auto-detect and enable for all frameworks
preflight version                 # show version
```

### REST API

```bash
# Start the server
preflight serve --port 8100

# Evaluate an action
curl -X POST http://localhost:8100/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "tool_name": "delete_records",
    "arguments": {"table": "users"},
    "intent": {
      "goal": "Clean up inactive users",
      "reasoning_summary": "Monthly cleanup",
      "irreversible": true,
      "confidence": 0.6
    }
  }'

# View passports
curl http://localhost:8100/passports

# Pipeline stats
curl http://localhost:8100/stats
```

### Dashboard

```bash
preflight dashboard --port 8200
# Open http://localhost:8200
```

Real-time monitoring with action timeline, risk charts, passport logs, and policy violations.

---

## Policy engine

Define rules in Python or YAML. Think OPA (Open Policy Agent) for AI agents.

```python
from agent_preflight import PolicyEngine, Policy, RiskLevel, ActionType

engine = PolicyEngine()

# Block dangerous operations
engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
engine.add(Policy.deny("No critical risk").when(risk_level=RiskLevel.CRITICAL))

# Require human review
engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))

# Budget enforcement
engine.add(Policy.budget_limit("Max $50", max_cost=50.0))

# Prevent infinite loops
engine.add(Policy.max_actions("Too many actions", limit=20))

# Custom rules
engine.add(
    Policy.deny("No external emails")
    .when_custom(lambda a: a.name == "send_email" and "gmail" in str(a.args))
)

result = engine.evaluate(plan)
if result.blocked:
    print(result.summary())
```

---

## Audit trail

Every action. Every decision. Every passport. Queryable.

```python
from agent_preflight import AuditLog

audit = AuditLog("./preflight.db", backend="sqlite")

# Record
audit.record(plan, verdict="approved", actor="deploy-bot@acme.com")

# Query
recent = audit.query(last_n=10)
critical = audit.query(risk_level=RiskLevel.CRITICAL)
denied = audit.query(verdict="denied")
```

---

## LLM-powered semantic analysis

Go beyond pattern matching. Use an LLM to reason about what your agent is actually doing.

```python
from agent_preflight import SemanticAnalyzer

analyzer = SemanticAnalyzer(provider="openai", model="gpt-4")
analysis = analyzer.analyze(plan)

print(analysis.summary)           # Overall risk assessment
print(analysis.concerns)          # Specific safety concerns
print(analysis.recommendations)   # How to reduce risk
```

---

## Install

```bash
pip install agent-preflight                # core (zero dependencies except pydantic)
pip install agent-preflight[openai]        # + OpenAI integration
pip install agent-preflight[anthropic]     # + Anthropic integration
pip install agent-preflight[langchain]     # + LangChain integration
pip install agent-preflight[server]        # + FastAPI server & dashboard
pip install agent-preflight[all]           # everything
```

Python 3.10+. Zero required dependencies beyond pydantic.

---

## Architecture

```
agent_preflight/
├── core.py                 # Preflight engine (sync + async)
├── models.py               # ActionCapture, Plan, DependencyGraph
├── classifiers.py          # Heuristic risk classifiers
├── renderer.py             # Terraform-style terminal output
├── policy.py               # Policy engine with rule DSL
├── audit.py                # Audit trail (JSON + SQLite)
├── semantic.py             # LLM-powered semantic analysis
├── auto.py                 # Universal auto-detect for all frameworks
├── cli.py                  # CLI entry point
├── atf/                    # Autonomous Trust Fabric
│   ├── gateway.py          # Central orchestrator
│   ├── risk_engine.py      # Fast risk scoring (<1ms)
│   ├── intent_compiler.py  # Intent validation & embedding
│   ├── simulation.py       # Monte Carlo engine
│   ├── drift.py            # Anomaly detection
│   ├── mirror_world.py     # Sandbox execution
│   ├── passport.py         # HMAC-signed audit artifacts
│   ├── feedback.py         # Correction suggestions
│   ├── policy_v2.py        # YAML-based policy engine
│   ├── database.py         # SQLite persistence
│   └── plugins/            # Simulation domain plugins
│       ├── filesystem.py   # Filesystem cascade detection
│       ├── api_cost.py     # API cost explosion
│       ├── dependency.py   # Dependency graph analysis
│       ├── memory.py       # Memory runaway detection
│       └── infrastructure.py  # Infrastructure mutation
├── integrations/
│   ├── openclaw.py         # OpenClaw (zero-config)
│   ├── openai_hook.py      # OpenAI function calling
│   ├── anthropic_hook.py   # Anthropic tool_use
│   └── langchain.py        # LangChain callback
├── federation/             # Cross-org risk sharing (experimental)
└── dashboard/              # Real-time monitoring UI
```

---

## API reference

### `Preflight(auto_classify=True, max_actions=100, cost_limit=None)`

Core engine. Intercepts, classifies, and plans.

### `@pf.intercept` / `@pf.intercept(cost=0.05, reversible=False)`

Decorator to register tools for interception.

### `pf.dry_run(run_fn, task="")` / `await pf.async_dry_run(run_fn, task="")`

Capture all tool calls without executing them. Returns a `Plan`.

### `Plan`

- `.actions` — List of captured actions
- `.overall_risk` — Highest risk level
- `.irreversible_count` — Number of irreversible actions
- `.warnings` — Auto-generated warnings
- `.dependency_graph` — Execution order, cycles, critical path
- `.approve()` / `.execute()` — Gate and run
- `.to_json()` — Export for CI/CD

### `enable_preflight(mode="safe")`

One-line OpenClaw integration. Returns `OpenClawPreflight` instance.

### `ATFGateway`

Full pipeline orchestrator with risk engine, simulation, drift detection, policy enforcement, mirror world, and passport issuance.

---

## Roadmap

- [ ] MCP (Model Context Protocol) tool wrapper
- [ ] GitHub Action for CI/CD gating
- [ ] Webhook notifications (Slack, Teams)
- [ ] Multi-agent fleet management
- [ ] Federation network for cross-org risk sharing
- [ ] CrewAI native integration
- [ ] AutoGen native integration
- [ ] VS Code extension

---

## License

MIT
