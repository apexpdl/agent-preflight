<div align="center">

# Preflight

### An AI agent just deleted your production database.

**Who approved that action? Where's the audit trail? Can you prove intent?**

Preflight answers those questions — *before the damage happens.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen.svg)]()
[![PyPI](https://img.shields.io/badge/pypi-v2.0.0-blue.svg)](https://pypi.org/project/agent-preflight/)

[Quick Start](#quick-start) | [How It Works](#how-it-works) | [Demo](#see-it-work) | [Architecture](ARCHITECTURE.md) | [Security](SECURITY.md)

</div>

---

## See It Work

```
$ python deploy_bot.py

 🤖 Agent: "Deleting inactive user records from production..."

 ┌─────────────────────────────────────────────────────────┐
 │  PREFLIGHT INTERCEPT                                    │
 │                                                         │
 │  Action:    delete_database_records                     │
 │  Target:    users table (production)                    │
 │  Intent:    "Remove inactive user accounts"             │
 │                                                         │
 │  Risk Score:  ████████████████████████░░  0.94          │
 │                                                         │
 │  ⚠ Irreversible action    (weight: 3.0x)               │
 │  ⚠ Destructive tool       (weight: 2.5x)               │
 │  ⚠ Production environment (weight: 2.0x)               │
 │                                                         │
 │  Simulation: 73% failure rate across 100 rollouts       │
 │  Drift:      Action deviates from agent's history       │
 │                                                         │
 │  ╔═══════════════════════════════════════════╗          │
 │  ║  VERDICT: BLOCKED                         ║          │
 │  ╚═══════════════════════════════════════════╝          │
 │                                                         │
 │  → Use SELECT first, then DELETE with WHERE clause      │
 │  → Run in staging before production                     │
 │  → Passport: a7c3e891 (chain: #14207)                  │
 └─────────────────────────────────────────────────────────┘

 🤖 Agent: "Understood. Running SELECT COUNT(*) in staging first."
```

**2 lines of code. Zero config. The agent corrects itself.**

---

## Quick Start

```bash
pip install agent-preflight
```

```python
from agent_preflight.auto import enable

enable()  # Every tool call is now governed. That's it.
```

Preflight auto-detects OpenAI, Anthropic, LangChain, CrewAI, and AutoGen. No config needed.

Or use an environment variable:

```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

<details>
<summary><strong>Framework-specific setup</strong></summary>

```python
# OpenAI
from agent_preflight.integrations.openai_hook import PreflightOpenAI
hook = PreflightOpenAI()
hook.register_tool("send_email", send_email_fn)

# Anthropic
from agent_preflight.integrations.anthropic_hook import PreflightAnthropic
hook = PreflightAnthropic()
hook.register_tool("search_db", search_db_fn)

# LangChain / LangGraph
from agent_preflight.integrations.langchain import PreflightCallbackHandler
handler = PreflightCallbackHandler()
agent.invoke({"input": "..."}, config={"callbacks": [handler.handler]})

# MCP (Model Context Protocol)
from agent_preflight.mcp import PreflightMCPMiddleware
middleware = PreflightMCPMiddleware()
result = await middleware.handle(tool_call, executor=tool_fn)
```

</details>

---

## The Problem

AI agents are executing real-world actions with **zero governance**.

They delete production databases. They wire money to wrong accounts. They run shell commands that destroy infrastructure. Not because models are malicious — because **no system exists between what an agent decides and what it does.**

Observability tools watch *after* the damage. Permission systems block *everything*. Neither works for autonomous agents that must act in real-time, at scale, with varying levels of risk.

**Preflight is the missing layer.** It evaluates every action *before execution*, scores its risk, simulates consequences, and produces a cryptographic audit trail of every decision.

---

## How It Works

Every tool call runs through a six-stage governance pipeline in **under 15ms**:

```
          Agent makes a tool call
                   │
          ┌────────▼────────┐
          │  INTENT COMPILER │──── Validates declared intent against arguments
          └────────┬────────┘
          ┌────────▼────────┐
          │   RISK ENGINE   │──── 12-signal scoring, sub-millisecond, no LLM calls
          └────────┬────────┘
          ┌────────▼────────┐
          │   SIMULATION    │──── Monte Carlo rollouts: failure probability + cascades
          └────────┬────────┘
          ┌────────▼────────┐
          │ DRIFT DETECTION │──── Isolation-forest anomaly flagging
          └────────┬────────┘
          ┌────────▼────────┐
          │  POLICY ENGINE  │──── "No prod deletes." "Max $500." YAML or Python.
          └────────┬────────┘
          ┌────────▼────────┐
          │  MIRROR WORLD   │──── Sandboxed execution, result vs. intent comparison
          └────────┬────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     ALLOW       WARN       BLOCK
   Passport    Passport   Correction
    issued      issued     returned
```

---

## What Gets Blocked (and What Doesn't)

| Risk | Score | Verdict | Examples |
|---|---|---|---|
| **Safe** | 0.0 – 0.3 | ALLOW | `get_user()`, `read_file()`, `search()` |
| **Moderate** | 0.3 – 0.6 | WARN + log | `update_database()`, `send_notification()` |
| **Dangerous** | 0.6 – 0.8 | BLOCK + suggest | `delete_records()`, `exec_shell()` |
| **Critical** | 0.8 – 1.0 | Hard BLOCK | `drop_table()`, `wire_transfer($50k)` |

Risk scoring is pure computation. No LLM calls. Sub-millisecond.

<details>
<summary><strong>12 risk signals</strong></summary>

| Signal | Weight | Triggers On |
|---|---|---|
| Irreversible action | 3.0x | `send_email`, `wire_transfer`, `publish` |
| Destructive tool | 2.5x | `delete`, `drop`, `truncate`, `rm` |
| Financial operation | 2.8x | `pay`, `transfer`, `charge`, `wire` |
| Shell execution | 2.2x | `exec`, `bash`, `system`, `eval` |
| Sensitive path | 2.0x | `.env`, `/etc/`, `prod`, `credentials` |
| High cost | 1.8x | Estimated cost > $100 |
| Low confidence | 1.5x | Agent confidence < 50% |
| Drift anomaly | 2.0x | Deviation from historical patterns |

</details>

---

## Action Passport — Cryptographic Proof of Every Decision

Every governed action produces a signed, tamper-proof audit artifact:

```json
{
  "passport_id": "a7c3e891-4f2d-4b8a-9e1c-3d5f7a2b8c4e",
  "agent": { "agent_id": "deploy-bot-7", "framework": "anthropic" },
  "action": {
    "tool_name": "delete_database_records",
    "arguments": { "table": "users", "env": "production" },
    "intent": { "goal": "Remove inactive user accounts", "reversible": false }
  },
  "risk_assessment": {
    "composite_score": 0.94,
    "simulation": { "rollouts": 100, "failure_rate": 0.73 }
  },
  "verdict": { "decision": "block", "reason": "Irreversible deletion of production data." },
  "signatures": { "algorithm": "Ed25519", "policy_signature": "3a8f...c2d1" },
  "chain": { "previous_hash": "7b2e...9f4a", "sequence_number": 14207 }
}
```

Passports are stored in an **append-only, chain-hashed ledger**. Each record links to the previous via SHA-256. Designed for court-admissible evidence and regulatory audit.

---

## Policy Engine

Declarative rules. No code changes required.

```python
from agent_preflight import PolicyEngine, Policy, RiskLevel, ActionType

engine = PolicyEngine()
engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
engine.add(Policy.deny("No critical risk").when(risk_level=RiskLevel.CRITICAL))
engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))
engine.add(Policy.budget_limit("Max $500", max_cost=500.0))
```

---

## Performance

No LLM calls in the critical path. Your agents don't slow down.

| Operation | p50 | p95 | p99 |
|---|---|---|---|
| Risk scoring (12 signals) | 0.3ms | 0.8ms | 1.2ms |
| Full pipeline (low risk) | 2.1ms | 4.7ms | 6.3ms |
| Full pipeline (high risk + simulation) | 8.4ms | 14.2ms | 18.6ms |
| Passport signing (Ed25519) | 0.4ms | 0.7ms | 1.1ms |
| Ledger verification (10K records) | 42ms | 58ms | 71ms |

---

## Enterprise Features

| Feature | What It Does |
|---|---|
| **Ed25519 Signing** | Every passport dual-signed. Key rotation + revocation built in. |
| **Liability Ledger** | Chain-hashed, append-only. Tamper detection. Forensic-ready. |
| **Multi-Tenant** | Org → team → project isolation. Separate ledgers, policies, budgets. |
| **M-of-N Consensus** | High-risk actions require multiple human approvals. Signed votes. |
| **Deterministic Replay** | Reproduce any past execution exactly. Export for incident review. |
| **Cost Governance** | Per-tenant budget caps, token tracking, auto-blocking at limits. |
| **Observability** | Prometheus metrics, OpenTelemetry spans, structured logging. |

---

## Regulatory Alignment

| Framework | How Preflight Helps |
|---|---|
| **EU AI Act** | Risk classification, human oversight, audit trails, transparency |
| **SOC 2** | Access controls, audit logging, change management, monitoring |
| **ISO 27001** | Information security controls, risk assessment, incident management |
| **NIST AI RMF** | Risk measurement, governance, transparency, accountability |

---

## Comparison

|  | Preflight | Agent Frameworks | Tool Wrappers | Monitoring Tools |
|---|---|---|---|---|
| Pre-execution risk scoring | **Yes** | No | No | No |
| Monte Carlo simulation | **Yes** | No | No | No |
| Cryptographic audit trail | **Yes** | No | No | No |
| Policy engine | **Yes** | Partial | No | No |
| Drift detection | **Yes** | No | No | Partial |
| Sandbox execution | **Yes** | No | Partial | No |
| Multi-tenant isolation | **Yes** | No | No | Partial |
| Operator consensus | **Yes** | No | No | No |

---

## Deployment

```bash
# Docker
docker build -t preflight . && docker run -p 8000:8000 preflight

# Docker Compose (with Prometheus + Grafana)
docker-compose up
# Preflight: localhost:8000 | Prometheus: localhost:9090 | Grafana: localhost:3000

# Kubernetes
helm install preflight deploy/helm/preflight/
```

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/execute` | Evaluate an action through the full pipeline |
| `GET` | `/passports` | Query issued action passports |
| `GET` | `/ledger` | Query the liability ledger |
| `GET` | `/ledger/verify` | Verify ledger chain integrity |
| `GET` | `/consensus/pending` | Pending approval requests |
| `POST` | `/consensus/{id}/approve` | Approve a high-risk action |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/health` | Health status |

---

## Demo

Interactive demo for simulating agent actions and visualizing governance decisions:

```bash
cd demo/backend && uvicorn app:app --port 8100  # Backend
cd demo/frontend && npm install && npm run dev   # Frontend
```

Choose from pre-built scenarios — "Delete Production DB", "Transfer $50,000", "Execute Shell Command" — or build custom actions.

---

## Preflight Is Not

- ~~A prompt library~~ — Infrastructure.
- ~~A model wrapper~~ — Framework-agnostic.
- ~~A chatbot framework~~ — For agents that act.
- ~~A logging tool~~ — Pre-execution, not post-mortem.
- ~~A compliance checklist~~ — Runtime enforcement.

---

## Architecture

```
agent_preflight/                 Core governance pipeline
  atf/
    gateway.py                   Pipeline orchestrator
    risk_engine.py               12-signal weighted risk scoring (<1ms)
    simulation.py                Monte Carlo engine (50-200 rollouts)
    drift.py                     Isolation-forest anomaly detection
    policy_v2.py                 YAML/Python declarative policy engine
    mirror_world.py              Sandboxed execution + intent verification
    passport.py                  Ed25519/HMAC-SHA256 signed passports
    intent_compiler.py           Structured intent validation
    plugins/                     Domain simulation plugins
  integrations/                  Framework hooks (OpenAI, Anthropic, LangChain, CrewAI, AutoGen)
  mcp/                           Model Context Protocol adapter + middleware
  core.py                        High-level Preflight API
  auto.py                        Zero-config framework detection

trust_kernel/                    Enterprise governance layer
cloud/                           Multi-tenant cloud infrastructure
demo/                            Interactive demo application
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design, data flow diagrams, and deployment topology.

---

## Roadmap

- [x] Six-stage governance pipeline
- [x] OpenAI, Anthropic, LangChain, CrewAI, AutoGen integrations
- [x] Ed25519 cryptographic signatures + chain-hashed ledger
- [x] Multi-tenant architecture with RBAC
- [x] M-of-N operator consensus
- [x] Prometheus + OpenTelemetry observability
- [x] MCP adapter + middleware
- [x] Docker, Docker Compose, Kubernetes deployment
- [ ] Node.js / TypeScript SDK
- [ ] PostgreSQL ledger backend
- [ ] VS Code extension with inline risk display
- [ ] Preflight Cloud (hosted multi-tenant SaaS)
- [ ] Multi-agent fleet dashboard
- [ ] Federation protocol for cross-org risk sharing

---

## Install

```bash
pip install agent-preflight                # Core (zero deps beyond pydantic)
pip install agent-preflight[openai]        # + OpenAI
pip install agent-preflight[anthropic]     # + Anthropic
pip install agent-preflight[langchain]     # + LangChain
pip install agent-preflight[server]        # + FastAPI server
pip install agent-preflight[all]           # Everything
```

Python 3.10+. Zero required dependencies beyond pydantic.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) and [THREAT_MODEL.md](docs/THREAT_MODEL.md).

## License

MIT
