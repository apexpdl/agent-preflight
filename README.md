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

**Or zero code changes:**

```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

---

## What happens when your agent goes rogue

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⛔  PREFLIGHT  BLOCKED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tool:    delete_database_records
  Risk:    ████████████████████░░░░ 87%
  Flags:   irreversible, destructive tool, sensitive path
  Reason:  CRITICAL RISK: This action scores 87% risk.
  ──────────────────────────────────────────────────────────
  Suggested fix:
    → Use a safer alternative to destructive operations
    → Split into read-verify-then-delete pattern
    → Target a less sensitive path or use staging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  3ms │ passport:a1b2c3d4
```

Low-risk actions (reading files, fetching profiles) pass through **silently**. No popups. No interruptions. Your agent runs at full speed.

High-risk actions get **blocked with suggestions** for safer alternatives. You only see Preflight when it matters.

---

## Why this exists

Real incidents. Real money lost.

- **$47K** burned by a recursive agent loop running 11 days unnoticed
- **Production databases** deleted by coding agents despite freeze instructions
- **$2.3M** in fraudulent wire transfers approved by AI assistants
- **1,184 malicious agent skills** found on package registries

Every incident had the same root cause: **nobody saw what the agent was about to do.**

---

## Integration (pick one)

### Zero config (recommended)

```bash
PREFLIGHT_AUTO=1 python my_agent.py
```

No code changes. Preflight detects installed frameworks and wraps them automatically.

### One line

```python
from agent_preflight.integrations.openclaw import enable_preflight
enable_preflight()
```

### Import hook (zero code changes)

```python
import agent_preflight.hook  # auto-wraps OpenClaw on import
```

### Auto-detect all frameworks

```python
from agent_preflight.auto import enable
enable()  # wraps OpenClaw, LangChain, CrewAI, AutoGen — whatever's installed
```

---

## Works with everything

**OpenClaw** — 1 line. **OpenAI** — function calling hook. **Anthropic** — tool_use hook. **LangChain** — callback handler. **Any Python agent** — `@pf.intercept` decorator.

```python
# OpenAI
from agent_preflight.integrations.openai_hook import PreflightOpenAI
hook = PreflightOpenAI(Preflight())
hook.register_tool("send_email", send_email_fn)
hook.capture_from_response(response)

# Anthropic
from agent_preflight.integrations.anthropic_hook import PreflightAnthropic
hook = PreflightAnthropic(Preflight())
hook.capture_from_response(response)

# LangChain
from agent_preflight.integrations.langchain import PreflightCallbackHandler
handler = PreflightCallbackHandler(Preflight())

# Any Python agent
pf = Preflight()

@pf.intercept
def send_email(to, subject, body):
    smtp.send(to, subject, body)

plan = pf.dry_run(my_workflow, task="Send report")
print(pf.format(plan))
plan.approve()
plan.execute()
```

---

## Risk Memory — Preflight gets smarter

**No other agent safety tool does this.**

Every time Preflight blocks an action, it remembers the pattern. Next time a similar action comes in — from any agent, any session — the risk score is automatically adjusted upward.

```
First time:   delete_records() → Risk 72% → BLOCKED
Second time:  delete_records() → Risk 85% → BLOCKED (pattern_blocked_1_times)
Third time:   delete_records() → Risk 91% → BLOCKED (tool_frequently_blocked)
```

Preflight learns from:
- Exact pattern matches (same tool + same argument keys)
- Tool-level history (what % of calls to this tool get blocked?)
- Recent block clusters (same tool blocked 3 times in 5 minutes?)

This means your safety layer gets **more opinionated over time**, not less.

---

## Smart interruptions

Preflight doesn't ask "are you sure?" for everything.

| Risk level | What happens | Example |
|-----------|-------------|---------|
| **Low** (0-30%) | Passes silently | `get_user()`, `read_file()`, `search()` |
| **Medium** (30-60%) | Warning + allows | `update_database()`, `send_notification()` |
| **High** (60-80%) | Blocks + suggests | `delete_records()`, `exec_shell()` |
| **Critical** (80%+) | Hard block | `drop_table()`, `wire_transfer()`, `rm -rf` |

If the **user** explicitly asked the agent to do something, Preflight gives it more trust. If the **agent** decided autonomously, Preflight is more cautious.

---

## The full pipeline (for the technically curious)

6 stages. Under 5ms for low-risk actions.

```
Agent action
    │
    ├─ 1. INTENT COMPILER ──── Validates what the agent says it's doing
    ├─ 2. RISK MEMORY ──────── "Have we seen this pattern fail before?"
    ├─ 3. RISK ENGINE (<1ms) ─ Weighted scoring: destructive? financial? shell?
    ├─ 4. SIMULATION ────────── Monte Carlo: 50-200 rollouts
    ├─ 5. POLICY ENGINE ────── YAML rules: "No prod deletes", "Max $500"
    ├─ 6. MIRROR WORLD ─────── Runs action in sandbox, compares to intent
    │
    └─ VERDICT: ALLOW / WARN / BLOCK
         ├── ALLOWED → Signed Action Passport (HMAC-SHA256)
         └── BLOCKED → Correction with safer alternatives
```

### Risk scoring

Pure computation, no LLM calls. Under 1ms.

| Signal | Weight | Example |
|--------|--------|---------|
| Irreversible action | 3.0x | `send_email`, `wire_transfer` |
| Destructive tool | 2.5x | `delete`, `drop`, `truncate`, `rm` |
| Financial operation | 2.8x | `pay`, `transfer`, `charge`, `wire` |
| Shell execution | 2.2x | `exec`, `bash`, `system`, `eval` |
| Mass operation | 2.3x | `bulk`, `batch`, `mass`, `flush` |
| Dangerous arguments | 2.5x | `DROP TABLE`, `rm -rf`, `sudo` |
| Sensitive path | 2.0x | `.env`, `/etc/`, `prod`, `credentials` |
| Filesystem writes | 1.8x | `write_file`, `overwrite`, `chmod` |
| High cost | 1.8x | Estimated cost > $100 |
| Low confidence | 1.5x | Agent confidence < 50% |
| Drift similarity | 2.0x | Similar to past failures |

### Monte Carlo simulation

50-200 scenarios with random perturbations:
- Filesystem cascades, API cost explosions, dependency breaks
- Memory runaway, infrastructure mutations
- Returns failure probability, cascade risk, volatility index

### Action Passports

Every allowed action gets a signed, tamper-proof audit artifact (HMAC-SHA256). Verifiable. Auditable. Compliance-ready.

---

## CLI

```bash
preflight demo                   # interactive demo
preflight atf                    # full ATF pipeline (screenshot-worthy)
preflight status                 # what's detected, what's active
preflight explain delete_records # why would this tool be flagged?
preflight doctor                 # diagnose setup issues
preflight auto                   # auto-detect and enable
preflight serve --port 8100      # REST API server
preflight dashboard --port 8200  # monitoring dashboard
preflight check script.py        # analyze a script
preflight audit ./trail          # view audit history
preflight enable --openclaw      # OpenClaw integration guide
```

---

## Policy engine

```python
from agent_preflight import PolicyEngine, Policy, RiskLevel, ActionType

engine = PolicyEngine()
engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
engine.add(Policy.deny("No critical risk").when(risk_level=RiskLevel.CRITICAL))
engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))
engine.add(Policy.budget_limit("Max $50", max_cost=50.0))
engine.add(Policy.max_actions("Loop guard", limit=20))

result = engine.evaluate(plan)
if result.blocked:
    print(result.summary())
```

---

## Audit trail

```python
from agent_preflight import AuditLog

audit = AuditLog("./preflight.db", backend="sqlite")
audit.record(plan, verdict="approved", actor="deploy-bot@acme.com")
recent = audit.query(last_n=10)
```

---

## Install

```bash
pip install agent-preflight                # core (pydantic only)
pip install agent-preflight[server]        # + FastAPI dashboard & API
pip install agent-preflight[openai]        # + OpenAI integration
pip install agent-preflight[anthropic]     # + Anthropic integration
pip install agent-preflight[langchain]     # + LangChain integration
pip install agent-preflight[all]           # everything
```

Python 3.10+

---

## Architecture

```
agent_preflight/
├── core.py                 # Preflight engine
├── display.py              # Screenshot-worthy terminal output
├── hook.py                 # Zero-config import hook
├── auto.py                 # Universal framework auto-detect
├── cli.py                  # CLI (demo, status, explain, doctor)
├── atf/
│   ├── gateway.py          # Pipeline orchestrator
│   ├── risk_engine.py      # Fast risk scoring (<1ms)
│   ├── risk_memory.py      # Learns from past decisions
│   ├── simulation.py       # Monte Carlo engine
│   ├── drift.py            # Anomaly detection
│   ├── mirror_world.py     # Sandbox execution
│   ├── passport.py         # HMAC-signed audit artifacts
│   ├── feedback.py         # Correction suggestions
│   └── plugins/            # Simulation domain plugins
├── integrations/
│   ├── openclaw.py         # OpenClaw (zero-config)
│   ├── openai_hook.py      # OpenAI
│   ├── anthropic_hook.py   # Anthropic
│   └── langchain.py        # LangChain
└── dashboard/              # Real-time monitoring UI
```

---

## License

MIT
