<div align="center">

# Preflight

### The Execution Governance Layer for AI Agents

**The control plane between AI intent and real-world execution.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen.svg)]()
[![PyPI](https://img.shields.io/badge/pypi-v2.0.0-blue.svg)](https://pypi.org/project/agent-preflight/)

[Documentation](docs/) | [Architecture](ARCHITECTURE.md) | [Security](SECURITY.md) | [Quick Start](#quick-start) | [Demo](#demo)

---

**Every AI agent action -- risk-scored, simulated, and cryptographically verified before it touches the real world.**

</div>

---

## The Problem

AI agents are executing real-world actions with no governance layer.

They delete production databases. They wire money to wrong accounts. They run shell commands that destroy infrastructure. They do this not because models are malicious, but because **no system exists between what an agent decides and what it does.**

Observability tools watch *after* the damage. Permission systems *block everything*. Neither approach works for autonomous agents that must act in real-time, at scale, with varying levels of risk.

The missing layer is **execution governance** -- a system that evaluates every action *before execution*, scores its risk, simulates its consequences, verifies its alignment with declared intent, and produces a cryptographic audit trail of every decision.

Preflight is that layer.

---

## What Happens Without Governance

```
Agent                                          Production
  |                                                |
  |   "delete all user records"                    |
  |----------------------------------------------->|
  |                                                |   Records deleted.
  |                                                |   No audit trail.
  |                                                |   No rollback.
  |                                                |   No one verified.
```

## What Happens With Preflight

```
Agent          Preflight                               Production
  |                |                                       |
  |  tool call     |                                       |
  |--------------->|                                       |
  |                |---> Intent Compiler                   |
  |                |---> Risk Engine (sub-ms)              |
  |                |---> Monte Carlo Simulation            |
  |                |---> Drift Detection                   |
  |                |---> Policy Evaluation                 |
  |                |---> Mirror World Sandbox              |
  |                |                                       |
  |                |  VERDICT: BLOCK                       |
  |                |  Risk: 0.97                           |
  |                |  Flags: [irreversible, destructive]   |
  |                |                                       |
  |  correction    |                                       |
  |<---------------|                                       |
  |                |                                       |
  |  "Blocked. Use SELECT first, then DELETE              |
  |   with a WHERE clause in staging."                    |
```

---

## How It Works

Preflight intercepts every tool call your agent makes and runs it through a six-stage governance pipeline:

```
                         Action Envelope
                              |
                    +---------+---------+
                    |                   |
              1. INTENT COMPILER    Validates declared intent
                    |                against actual arguments
                    |
              2. RISK ENGINE        12-signal weighted scoring
                    |                Sub-millisecond. No LLM calls.
                    |
              3. SIMULATION         Monte Carlo rollouts (50-200)
                    |                Failure probability, cascade risk
                    |
              4. DRIFT DETECTION    Isolation-forest anomaly detection
                    |                Flags deviation from historical patterns
                    |
              5. POLICY ENGINE      Declarative rules (YAML/Python)
                    |                "No prod deletes", "Max $500 spend"
                    |
              6. MIRROR WORLD       Sandboxed execution
                    |                Compares result to declared intent
                    |
               +---------+
               | VERDICT  |
               +---------+
              /     |      \
           ALLOW   WARN   BLOCK
             |       |       |
         Passport  Passport  Correction
         issued    issued    returned
```

Every allowed action receives an **Action Passport** -- a cryptographically signed, tamper-proof audit artifact linking the agent, its intent, the risk assessment, and the execution outcome.

---

## Quick Start

```bash
pip install agent-preflight
```

```python
from agent_preflight.auto import enable

enable()  # Wraps all detected frameworks. Every tool call is now governed.
```

That's it. Preflight auto-detects OpenAI, Anthropic, LangChain, CrewAI, and AutoGen.

### Framework-Specific Setup

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

### Environment Variable Mode

```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

---

## Risk Scoring

Pure computation. No LLM calls. Sub-millisecond.

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

| Risk Level | Verdict | Example Actions |
|---|---|---|
| **0.0 -- 0.3** | ALLOW | `get_user()`, `read_file()`, `search()` |
| **0.3 -- 0.6** | WARN | `update_database()`, `send_notification()` |
| **0.6 -- 0.8** | BLOCK + suggest | `delete_records()`, `exec_shell()` |
| **0.8 -- 1.0** | Hard BLOCK | `drop_table()`, `wire_transfer()` |

---

## Action Passport

Every governed action produces a signed passport:

```json
{
  "passport_version": "1.0",
  "passport_id": "a7c3e891-4f2d-4b8a-9e1c-3d5f7a2b8c4e",
  "timestamp": "2026-03-10T14:23:07.441Z",
  "agent": {
    "agent_id": "deploy-bot-7",
    "framework": "anthropic"
  },
  "action": {
    "tool_name": "delete_database_records",
    "action_type": "delete",
    "arguments": { "table": "users", "env": "production" },
    "intent": {
      "goal": "Remove inactive user accounts",
      "confidence": 0.72,
      "reversible": false
    }
  },
  "risk_assessment": {
    "composite_score": 0.94,
    "components": {
      "tool_risk": 0.85,
      "irreversibility_risk": 1.0,
      "resource_risk": 0.90
    },
    "simulation": {
      "rollouts": 100,
      "failure_rate": 0.73,
      "confidence_interval": { "lower": 0.64, "upper": 0.81 }
    }
  },
  "verdict": {
    "decision": "block",
    "reason": "Irreversible deletion of production user data. Risk score 0.94 exceeds threshold."
  },
  "signatures": {
    "algorithm": "Ed25519",
    "policy_signature": "3a8f...c2d1"
  },
  "chain": {
    "previous_hash": "7b2e...9f4a",
    "record_hash": "c1d4...8e3b",
    "sequence_number": 14207
  }
}
```

Passports are stored in an append-only, chain-hashed ledger. Each record links to the previous via SHA-256, making tampering detectable. Designed for court-admissible evidence and regulatory audit.

See [Action Passport v1.0 Specification](specs/action-passport-v1.0.json).

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
  integrations/                  Framework hooks
    openai_hook.py               OpenAI function calling
    anthropic_hook.py            Anthropic tool_use
    langchain.py                 LangChain / LangGraph
    crewai_hook.py               CrewAI
    autogen_hook.py              AutoGen
  mcp/                           Model Context Protocol adapter
    adapter.py                   MCP-to-ATF bridge
    middleware.py                MCP server middleware
  core.py                        High-level Preflight API
  auto.py                        Zero-config framework detection

trust_kernel/                    Enterprise governance layer
  crypto.py                      Ed25519 + HMAC-SHA256 signing
  ledger.py                      Chain-hashed append-only audit ledger
  consensus.py                   M-of-N operator consensus
  multitenancy.py                Tenant isolation + RBAC
  cost_governor.py               Budget enforcement + token tracking
  reproducibility.py             Deterministic replay
  rollback.py                    Atomic state rollback
  api.py                         REST API with auth + rate limiting
  observability.py               Prometheus, OpenTelemetry, structured logging

cloud/                           Multi-tenant cloud infrastructure
  models/                        Tenant, user, API key models
  auth/                          Authentication layer
  api/                           Cloud API endpoints

demo/                            Interactive demo application
  backend/                       FastAPI simulation server
  frontend/                      React + Vite governance dashboard
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design, data flow diagrams, and deployment topology.

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

## Enterprise Features

### Cryptographic Verification

Every action passport is dual-signed with Ed25519 asymmetric keys (HMAC-SHA256 fallback for zero-dependency environments). Key rotation, revocation, and public key distribution for independent verification.

### Append-Only Liability Ledger

Chain-hashed audit trail where every record links to the previous via SHA-256. Integrity verification detects any tampering. Designed for regulatory compliance and forensic analysis.

### Multi-Tenant Isolation

Organization, team, and project-level isolation. Separate ledgers, policies, and budgets per tenant. RBAC with Owner, Operator, Auditor, and Viewer roles.

### M-of-N Operator Consensus

High-risk actions can require multiple human approvals before execution. Signed votes with cryptographic non-repudiation. Configurable thresholds per risk level.

### Deterministic Replay

Reproduce any past execution exactly. Export replay manifests for forensic analysis and incident review.

### Cost Governance

Per-tenant budget caps, token tracking, API call limits, and recursion depth controls. Automatic blocking when limits are reached.

---

## Observability

```bash
# Prometheus metrics
curl http://localhost:8000/metrics
# preflight_actions_total, preflight_risk_score, preflight_pipeline_duration_seconds

# OpenTelemetry spans
# OTLP-compatible export to Datadog, Grafana, New Relic, or any OTel backend

# Safety badge
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
# Preflight:  localhost:8000
# Prometheus: localhost:9090
# Grafana:    localhost:3000
```

### Kubernetes

```bash
helm install preflight deploy/helm/preflight/
# HPA autoscaling: 2-10 replicas based on CPU/memory
```

---

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
| `GET` | `/keys/public` | Public keys for passport verification |
| `POST` | `/keys/rotate/{role}` | Rotate signing keys |
| `GET` | `/health` | Component health status |
| `GET` | `/stats` | Execution statistics |

---

## Demo

An interactive demo application for simulating agent actions and visualizing governance decisions.

```bash
# Start the backend
cd demo/backend && uvicorn app:app --port 8100

# Start the frontend
cd demo/frontend && npm install && npm run dev
```

Choose from pre-built scenarios -- "Delete Production DB", "Transfer $50,000", "Execute Shell Command" -- or build custom actions. See risk scores, verdicts, risk factors, and full passport output in real time.

---

## Regulatory Alignment

Preflight's governance infrastructure maps to existing compliance frameworks:

| Framework | Relevant Controls |
|---|---|
| **EU AI Act** | Risk classification, human oversight, audit trails, transparency |
| **SOC 2** | Access controls, audit logging, change management, monitoring |
| **ISO 27001** | Information security controls, risk assessment, incident management |
| **NIST AI RMF** | Risk measurement, governance, transparency, accountability |

Action Passports provide the evidence chain required by auditors: who requested what, what risk was assessed, what decision was made, and the cryptographic proof that the record hasn't been altered.

---

## Benchmarks

Measured on standard workloads. No LLM calls in the critical path.

| Operation | p50 | p95 | p99 |
|---|---|---|---|
| Risk scoring (12 signals) | 0.3ms | 0.8ms | 1.2ms |
| Full pipeline (low risk) | 2.1ms | 4.7ms | 6.3ms |
| Full pipeline (high risk, simulation) | 8.4ms | 14.2ms | 18.6ms |
| Passport signing (HMAC-SHA256) | 0.1ms | 0.2ms | 0.3ms |
| Passport signing (Ed25519) | 0.4ms | 0.7ms | 1.1ms |
| Ledger integrity verification (10K records) | 42ms | 58ms | 71ms |

---

## Preflight Is Not

- A prompt library
- A model wrapper or LLM gateway
- A chatbot framework
- A logging-only tool
- A compliance checklist

Preflight is **infrastructure**. It sits between the agent and the world, evaluates every action in real time, and produces cryptographic proof of every decision.

---

## Comparison

|  | Preflight | Agent Frameworks | Tool Wrappers | Monitoring Tools |
|---|---|---|---|---|
| Pre-execution risk scoring | Yes | No | No | No |
| Monte Carlo simulation | Yes | No | No | No |
| Cryptographic audit trail | Yes | No | No | No |
| Policy engine | Yes | Partial | No | No |
| Drift detection | Yes | No | No | Partial |
| Sandbox execution | Yes | No | Partial | No |
| Multi-tenant isolation | Yes | No | No | Partial |
| Operator consensus | Yes | No | No | No |
| Works post-incident | Also | No | No | Only |

---

## Roadmap

- [x] Six-stage governance pipeline (risk, simulation, drift, policy, mirror, passport)
- [x] OpenAI, Anthropic, LangChain, CrewAI, AutoGen integrations
- [x] Ed25519 cryptographic signatures with key management
- [x] Chain-hashed append-only liability ledger
- [x] Multi-tenant architecture with RBAC
- [x] M-of-N operator consensus
- [x] Prometheus metrics + OpenTelemetry spans
- [x] Monte Carlo simulation with domain plugins
- [x] Policy engine (YAML + Python)
- [x] Docker, Docker Compose, Kubernetes deployment
- [x] Action Passport v1.0 specification
- [x] MCP (Model Context Protocol) adapter + middleware
- [ ] Node.js / TypeScript SDK
- [ ] PostgreSQL ledger backend
- [ ] VS Code extension with inline risk display
- [ ] Preflight Cloud (hosted multi-tenant SaaS)
- [ ] AI Near-Miss Index (public safety statistics)
- [ ] Multi-agent fleet dashboard
- [ ] Deterministic replay UI
- [ ] Federation protocol for cross-organization risk sharing

---

## Install

```bash
pip install agent-preflight                # Core (zero deps beyond pydantic)
pip install agent-preflight[openai]        # + OpenAI integration
pip install agent-preflight[anthropic]     # + Anthropic integration
pip install agent-preflight[langchain]     # + LangChain integration
pip install agent-preflight[server]        # + FastAPI server
pip install agent-preflight[all]           # Everything
```

Python 3.10+. Zero required dependencies beyond pydantic.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and how to add new pipeline stages, simulation plugins, or framework integrations.

---

## Security

See [SECURITY.md](SECURITY.md) for our security policy and responsible disclosure process. See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for the threat model.

---

## Why Preflight Exists

Autonomous AI agents are being deployed into production environments with the ability to execute real-world actions: database operations, financial transactions, infrastructure changes, external API calls. The number of these deployments is growing exponentially. The governance infrastructure is not.

Every major AI incident in the last two years shares the same root cause: an agent executed an action that no system verified before execution. Not after. Before.

Preflight exists because the gap between what agents can do and what they should do will only widen. The infrastructure to govern that gap must exist as an independent layer -- not embedded in any single framework, not dependent on any single model provider, not limited to any single deployment topology.

This is not a feature. It is infrastructure. And it must be open.

---

## License

MIT

