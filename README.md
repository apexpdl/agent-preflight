# Preflight

**The execution firewall for AI agents.**

One line of code. Zero config. Every AI agent action is risk-scored, simulated, and verified before it touches the real world.

```
pip install agent-preflight
```

```python
from agent_preflight.integrations.openclaw import enable_preflight

enable_preflight()  # done. every tool call is now safe.
```

No architecture diagrams. No config files. No PhD required.

---

## The Problem

Real incidents. Real money lost. Real damage done.

- **$47K** burned by a recursive agent loop running 11 days unnoticed
- **Production databases** deleted by coding agents despite freeze instructions
- **$2.3M** in fraudulent wire transfers approved by AI assistants
- **1,184 malicious agent skills** found on package registries

Every incident had the same root cause: **nobody verified what the agent was about to do.**

Observability tools watch *after*. Security tools *block everything*. Preflight **verifies the plan and only blocks what's actually dangerous.**

---

## How It Works

Every time your agent tries to do something — send an email, delete a record, make an API call — Preflight intercepts it:

```
Your agent wants to: delete_database_records(table="users", env="prod")

Preflight says:
  Risk:     99.8%
  Verdict:  BLOCKED
  Flags:    [irreversible, destructive_tool, sensitive_path]
  Why:      "Deleting production database records is irreversible.
             Try reading first, then deleting with a WHERE clause."
```

Low-risk actions pass through **silently**. High-risk actions get **blocked with safer alternatives**.

| Risk Level | What Happens | Example |
|-----------|-------------|---------|
| **Low** (0-30%) | Passes silently | `get_user()`, `read_file()`, `search()` |
| **Medium** (30-60%) | Warning + allows | `update_database()`, `send_notification()` |
| **High** (60-80%) | Blocks + suggests alternative | `delete_records()`, `exec_shell()` |
| **Critical** (80%+) | Hard block + correction | `drop_table()`, `wire_transfer()` |

---

## Works With Everything

### OpenClaw (1 line)
```python
from agent_preflight.integrations.openclaw import enable_preflight
enable_preflight()
```

### OpenAI Function Calling
```python
from agent_preflight.integrations.openai_hook import PreflightOpenAI

pf = Preflight()
hook = PreflightOpenAI(pf)
hook.register_tool("send_email", send_email_fn)
hook.capture_from_response(response)
plan = hook.build_plan(task="Send report")
```

### Anthropic Tool Use
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
```

### CrewAI
```python
from agent_preflight.integrations.crewai_hook import PreflightCrewAI

hook = PreflightCrewAI()
safe_tool = hook.wrap_tool(my_tool)
# Use safe_tool in your CrewAI agent — all calls are governed
```

### AutoGen
```python
from agent_preflight.integrations.autogen_hook import PreflightAutoGen

hook = PreflightAutoGen()
safe_functions = hook.wrap_function_map(my_function_map)
# Pass safe_functions to your AutoGen agent
```

### Zero Config Auto-Detect
```python
from agent_preflight.auto import enable
enable()  # wraps OpenClaw, LangChain, CrewAI, AutoGen — whatever's installed
```

```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

---

## The Pipeline

When Preflight intercepts an action, it runs through 6 stages in under 5ms for low-risk actions:

```
Agent action
    |
    v
1. INTENT COMPILER -----> Validates what the agent says it's doing
    |
    v
2. RISK ENGINE (<1ms) --> 12-feature weighted scoring with sigmoid normalization
    |                      Destructive? Irreversible? Financial? Shell? Sensitive path?
    v
3. SIMULATION ENGINE ---> Monte Carlo: 50-200 rollouts simulating failure scenarios
    |                      Wilson confidence intervals for statistical rigor
    v
4. DRIFT INTELLIGENCE --> Isolation-forest anomaly detection against historical patterns
    |
    v
5. POLICY ENGINE -------> YAML/Python rules: "No prod deletes", "Max $500 spend"
    |
    v
6. MIRROR WORLD --------> Runs action in sandbox, compares result to declared intent
    |
    v
VERDICT: ALLOW / WARN / BLOCK
    |
    +-- If ALLOWED: Issues Ed25519-signed Action Passport (tamper-proof)
    +-- If BLOCKED: Returns correction with safer alternatives
```

### Risk Scoring

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
| Drift anomaly | 2.0x | Similar to past failures |

### Monte Carlo Simulation

50-200 simulated scenarios with random perturbations:
- Filesystem cascades (deleting files that other files depend on)
- API cost explosions (retry loops that multiply costs)
- Dependency breaks (removing packages other services need)
- Memory runaway (operations that eat all available RAM)
- Infrastructure mutations (changing configs that affect other services)

Returns failure probability, cascade risk, and volatility index.

---

## Enterprise Features

### Preflight Kernel

The enterprise execution layer adds cryptographic verification, compliance infrastructure, and multi-tenant isolation.

#### Ed25519 Cryptographic Signatures
Every action gets dual-signed with Ed25519 asymmetric keys (falls back to HMAC-SHA256 for zero-dependency mode). Key rotation, revocation, and public key distribution for independent verification.

```python
from trust_kernel.crypto import CryptoProvider

crypto = CryptoProvider()
receipt = crypto.create_receipt(
    action_id="act-001",
    agent_id="deploy-bot",
    pre_state_hash="aabb...",
    post_state_hash="ccdd...",
    verdict="allow",
    risk_score=0.15,
)
assert crypto.verify_receipt(receipt)  # independent verification
```

#### Append-Only Liability Ledger
Chain-hashed, tamper-evident audit trail. Every record links to the previous via SHA-256 chain hash. Integrity verification detects any tampering.

#### Multi-Tenant Architecture
Organization, team, and project isolation. Separate ledgers, policies, and budgets per tenant. RBAC with Admin, Operator, Auditor, and Viewer roles.

```python
from trust_kernel.multitenancy import TenantManager, RBACManager

tm = TenantManager()
tenant, api_key = tm.create_tenant("Acme Corp", tier="enterprise")

rbac = RBACManager()
rbac.bind_user("alice", tenant.tenant_id, role="operator")
rbac.bind_user("bob", tenant.tenant_id, role="auditor")
```

#### M-of-N Operator Consensus
High-risk actions require multiple human approvals before execution. Signed votes with cryptographic non-repudiation.

#### Deterministic Replay
Reproduce any past execution exactly. Export replay manifests for forensic analysis.

#### Cost Governance
Per-tenant budget caps, token tracking, API call limits, and recursion depth controls.

---

## Observability

### Prometheus Metrics
```bash
curl http://localhost:8000/metrics
# preflight_actions_total, preflight_risk_score, preflight_pipeline_duration_seconds
```

### Structured Logging
JSON-structured audit trails with rotation and retention.

### OpenTelemetry Spans
OTLP-compatible span export for Datadog, Grafana, New Relic, or any OTel backend.

### Safety Snapshots
Shareable HTML safety reports with risk distribution charts and SVG badges.

```bash
curl http://localhost:8000/snapshot/badge.svg
```

---

## Deployment

### Docker
```bash
docker build -t preflight .
docker run -p 8000:8000 preflight
```

### Docker Compose (with Prometheus + Grafana)
```bash
docker-compose up
# Preflight: localhost:8000
# Prometheus: localhost:9090
# Grafana: localhost:3000
```

### Kubernetes (Helm)
```bash
helm install preflight deploy/helm/preflight/
# HPA autoscaling: 2-10 replicas based on CPU/memory
```

### GitHub Action
Add Preflight to your CI/CD pipeline. Every PR gets a safety score comment:
```yaml
# See .github/workflows/preflight-gate.yml
```

---

## Webhook Notifications

Real-time alerts when high-risk actions are detected:

```python
from agent_preflight.notifications.webhooks import NotificationManager

nm = NotificationManager()
nm.add_slack("https://hooks.slack.com/services/...")
nm.add_webhook("https://your-api.com/alerts")
# Automatic retry with exponential backoff + dead letter queue
```

---

## CLI

```bash
preflight demo                    # interactive demo
preflight atf                     # full pipeline demo
preflight serve --port 8100       # start REST API server
preflight dashboard --port 8200   # start monitoring dashboard
preflight check script.py         # analyze a script's agent actions
preflight audit ./trail           # view audit history
preflight auto                    # auto-detect and enable for all frameworks
preflight version                 # show version
```

---

## Policy Engine

```python
from agent_preflight import PolicyEngine, Policy, RiskLevel, ActionType

engine = PolicyEngine()
engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
engine.add(Policy.deny("No critical risk").when(risk_level=RiskLevel.CRITICAL))
engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))
engine.add(Policy.budget_limit("Max $50", max_cost=50.0))
```

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/execute` | Evaluate action through the full pipeline |
| `GET` | `/ledger` | Query the liability ledger |
| `GET` | `/ledger/verify` | Verify ledger chain integrity |
| `GET` | `/ledger/export/json` | Export for auditors |
| `GET` | `/consensus/pending` | Pending approval requests |
| `POST` | `/consensus/{id}/approve` | Approve a high-risk action |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/keys/public` | Public keys for verification |
| `POST` | `/keys/rotate/{role}` | Rotate signing keys |
| `GET` | `/snapshot/badge.svg` | SVG safety badge |
| `GET` | `/health` | Component health status |
| `GET` | `/stats` | Execution statistics |

---

## Install

```bash
pip install agent-preflight                # core (zero deps beyond pydantic)
pip install agent-preflight[openai]        # + OpenAI integration
pip install agent-preflight[anthropic]     # + Anthropic integration
pip install agent-preflight[langchain]     # + LangChain integration
pip install agent-preflight[server]        # + FastAPI server
pip install agent-preflight[all]           # everything
```

Python 3.10+. Zero required dependencies beyond pydantic.

---

## Architecture

```
agent_preflight/              # Developer Layer
├── core.py                   # Preflight engine (sync + async)
├── auto.py                   # Zero-config framework detection
├── atf/                      # Pipeline engine
│   ├── risk_engine.py        # <1ms risk scoring (12 features)
│   ├── simulation.py         # Monte Carlo (50-200 rollouts)
│   ├── drift.py              # Anomaly detection
│   ├── mirror_world.py       # Sandbox execution
│   ├── passport.py           # Signed Action Passports
│   ├── policy_v2.py          # YAML policy engine
│   └── plugins/              # Domain simulation plugins
├── integrations/             # Framework hooks
│   ├── openclaw.py           # OpenClaw (1 line)
│   ├── openai_hook.py        # OpenAI function calling
│   ├── anthropic_hook.py     # Anthropic tool_use
│   ├── langchain.py          # LangChain / LangGraph
│   ├── crewai_hook.py        # CrewAI
│   └── autogen_hook.py       # AutoGen
├── notifications/            # Slack, Teams, webhooks
└── federation/               # Cross-org risk sharing

trust_kernel/                 # Enterprise Layer
├── kernel.py                 # 13-stage orchestrator
├── crypto.py                 # Ed25519 + HMAC-SHA256 signing
├── ledger.py                 # Chain-hashed liability ledger
├── multitenancy.py           # Tenant isolation + RBAC
├── consensus.py              # M-of-N operator consensus
├── observability.py          # Prometheus, OTel, logging
├── snapshot.py               # Safety reports + SVG badges
├── api.py                    # REST API with auth + rate limiting
├── planner.py                # DAG execution planning
├── rollback.py               # Atomic rollback
├── cost_governor.py          # Budget enforcement
└── reproducibility.py        # Deterministic replay
```

---

## Specifications

- [Action Passport v1.0](specs/action-passport-v1.0.json) — Cryptographically signed audit artifact standard

---

## Roadmap

- [x] OpenClaw, OpenAI, Anthropic, LangChain integrations
- [x] CrewAI and AutoGen native integrations
- [x] Webhook notifications (Slack, Teams) with retry + dead letter queue
- [x] GitHub Action for CI/CD safety gating
- [x] Ed25519 cryptographic signatures with key management
- [x] Multi-tenant architecture with RBAC
- [x] Prometheus metrics + OpenTelemetry spans
- [x] Kubernetes Helm chart with HPA autoscaling
- [x] Docker + Docker Compose deployment
- [x] Action Passport v1.0 specification
- [x] Safety Snapshot generator (HTML, SVG badges)
- [x] Performance benchmark suite (p50/p95/p99)
- [ ] MCP (Model Context Protocol) server + middleware
- [ ] Node.js / TypeScript SDK
- [ ] VS Code extension with inline risk display
- [ ] PostgreSQL ledger backend
- [ ] Preflight Cloud (hosted SaaS)
- [ ] AI Near-Miss Index (public safety statistics)
- [ ] Multi-agent fleet dashboard

---

## License

MIT
