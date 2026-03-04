# agent-preflight

**Preview what your AI agent will do before it does it.**

The `terraform plan` for AI agents. Open-source middleware that intercepts tool calls, classifies risk, enforces policies, and shows a human-readable execution plan before anything touches the real world.

Works with **OpenAI**, **Anthropic**, **LangChain**, and any Python agent framework. Zero required dependencies.

```
================================================================
  PREFLIGHT PLAN    5 action(s)
  Send Q3 report to Sarah at Acme
================================================================

  WARNING: 3 irreversible action(s) in plan
  WARNING: DELETE on 'temp_reports' without prior READ - blind delete

     1. search_contacts  [READ]  [REVERSIBLE]
        query: 'Sarah from Acme'

  !! 2. send_email  [WRITE]  [IRREVERSIBLE]
        to: 'sarah@acme.com'
        subject: 'Q3 Performance Report'
        body: 'Hi Sarah, please find the Q3 report attached...'
        > External communication - cannot be unsent

  !  3. update_database  [WRITE]  [REVERSIBLE]
        query: "UPDATE invoices SET status='sent' WHERE quarter=...

  !! 4. delete_old_records  [DELETE]  [IRREVERSIBLE]
        table: 'temp_reports'
        before_date: '2025-01-01'
        > Destructive operation

  !  5. generate_image  [EXEC]  [IRREVERSIBLE]
        prompt: 'Professional header image for Q3 report'
        est. cost: $0.0800

================================================================
  Risk:    HIGH  (3 irreversible)
  Cost:    $0.0800 estimated
  Actions: 5 total
================================================================
```

## Why

Agents take irreversible actions with zero preview:

- **$47K** burned by a recursive agent loop that ran 11 days unnoticed
- **Production databases** deleted by coding agents despite freeze instructions
- **$2.3M** in fraudulent wire transfers approved by AI assistants
- **1,184 malicious agent skills** found on package registries

Every incident had the same root cause: nobody saw what the agent was about to do.

Observability tools watch *after*. Security tools *block*. Preflight **shows you the plan**.

## Install

```bash
pip install agent-preflight
```

With framework integrations:

```bash
pip install agent-preflight[openai]      # OpenAI function calling
pip install agent-preflight[anthropic]   # Anthropic tool_use
pip install agent-preflight[langchain]   # LangChain/LangGraph
pip install agent-preflight[all]         # Everything
```

## Quick Start

```python
from agent_preflight import Preflight

pf = Preflight()

# Wrap your agent's tools
@pf.intercept
def send_email(to, subject, body):
    smtp.send(to, subject, body)

@pf.intercept
def update_database(query):
    db.execute(query)

@pf.intercept(cost=0.08)
def generate_image(prompt):
    return dalle.generate(prompt)

# Run your agent in dry-run mode
plan = pf.dry_run(my_agent_workflow, task="Send Q3 report")

# See the full plan before anything executes
print(pf.format(plan))

# Approve and execute
plan.approve()
plan.execute()
```

## Core Features

### Action Classification

Automatically detects risk level, reversibility, and action type from function names and arguments.

- `send_email` -> IRREVERSIBLE, HIGH risk
- `get_users` -> READ, LOW risk
- `DROP TABLE` in args -> CRITICAL risk
- `DELETE FROM table;` without WHERE -> CRITICAL

### Loop Detection

Flags when the same tool is called 3+ times, catching runaway agent loops before they become $47K bills.

### Cost Tracking

Attach cost estimates to tools, set budget limits. Preflight warns when a plan exceeds your threshold.

### SQL Danger Detection

Catches `DROP TABLE`, `DELETE` without `WHERE`, `TRUNCATE`, and other destructive SQL patterns in arguments.

### Dependency Graph

Automatically tracks data flow between actions and builds a dependency graph:

```python
plan = pf.dry_run(workflow)
graph = plan.dependency_graph

graph.execution_order    # Safe execution order (topological sort)
graph.has_cycles         # Circular dependency detection
graph.critical_path      # Longest sequential chain
```

Detects dangerous patterns like **DELETE without prior READ** (blind deletes).

### Approve/Execute Flow

Plans must be explicitly approved before execution. No accidental runs.

### JSON Export

`plan.to_json()` for programmatic use, CI/CD integration, and audit trails. Includes dependency graph data.

### Async Support

Full async support for modern agent frameworks:

```python
@pf.intercept
async def fetch_api(url):
    return await httpx.get(url)

plan = await pf.async_dry_run(async_workflow, task="Fetch data")

# Async recording context manager
async with pf.async_recording(task="pipeline") as rec:
    await step_one()
    await step_two()
print(pf.format(rec.plan))
```

## Policy Engine

Declarative rules that evaluate plans and enforce organizational policies. Think OPA (Open Policy Agent) for AI agents.

```python
from agent_preflight import PolicyEngine, Policy, RiskLevel, ActionType

engine = PolicyEngine()

# Block dangerous operations
engine.add(Policy.deny("No DROP TABLE").when_args_match(r"DROP TABLE"))
engine.add(Policy.deny("No critical risk").when(risk_level=RiskLevel.CRITICAL))

# Require human review for destructive actions
engine.add(Policy.require_approval("Review deletes").when(action_type=ActionType.DELETE))

# Budget enforcement
engine.add(Policy.budget_limit("Stay under $50", max_cost=50.0))

# Action count limits (prevent infinite loops)
engine.add(Policy.max_actions("Too many actions", limit=20))

# Block all irreversible actions in staging
engine.add(Policy.no_irreversible("Staging is read-only"))

# Custom rules
engine.add(
    Policy.deny("No external emails")
    .when_custom(lambda a: a.name == "send_email" and "gmail" in str(a.args))
    .reason("Only internal emails allowed")
)

# Evaluate
result = engine.evaluate(plan)

if result.blocked:
    print(result.summary())    # Human-readable denial report
    sys.exit(1)

if result.needs_approval:
    # Route to human reviewer
    send_for_review(plan, result)

# Programmatic access
result.to_dict()  # For CI/CD integration
```

### Policy Types

| Method | Verdict | Use Case |
|--------|---------|----------|
| `Policy.deny(name)` | DENY | Block execution entirely |
| `Policy.require_approval(name)` | REQUIRE_APPROVAL | Flag for human review |
| `Policy.warn(name)` | WARN | Log warning but allow |
| `Policy.budget_limit(name, max_cost)` | DENY | Cost threshold |
| `Policy.max_actions(name, limit)` | DENY | Action count limit |
| `Policy.no_irreversible(name)` | DENY | Block irreversible actions |

### Conditions

```python
.when(risk_level=RiskLevel.CRITICAL)  # Match by attribute
.when(action_type=ActionType.DELETE)   # Match action type
.when(name=r"send_.*")                 # Regex match on name
.when_args_match(r"DROP TABLE")        # Regex match on arguments
.when_custom(lambda a: ...)            # Custom predicate
.reason("Explain why")                 # Custom denial message
```

## Audit Trail

Persist every plan evaluation for compliance, debugging, and analytics.

```python
from agent_preflight import AuditLog

# JSON file storage (one file per entry)
audit = AuditLog("./audit_trail")

# Or SQLite for production (indexed, queryable)
audit = AuditLog("./preflight.db", backend="sqlite")

# Record a plan evaluation
audit.record(
    plan,
    verdict="approved",
    actor="deploy-bot@acme.com",
    policy_result=result.to_dict(),
    metadata={"environment": "production", "run_id": "abc123"},
)

# Query history
recent = audit.query(last_n=10)
critical = audit.query(risk_level=RiskLevel.CRITICAL)
by_actor = audit.query(actor="john@acme.com")
denied = audit.query(verdict="denied")
last_hour = audit.query(since=time.time() - 3600)
```

View from CLI:

```bash
preflight audit ./preflight.db
```

## LLM-Powered Semantic Analysis

Go beyond heuristic pattern matching. Use an LLM to reason about the *meaning* of agent actions and their potential consequences.

```python
from agent_preflight import SemanticAnalyzer

# With OpenAI
analyzer = SemanticAnalyzer(provider="openai", model="gpt-4")

# With Anthropic
analyzer = SemanticAnalyzer(provider="anthropic", model="claude-sonnet-4-20250514")

# Or bring your own LLM function
analyzer = SemanticAnalyzer(llm_fn=my_custom_llm)

analysis = analyzer.analyze(plan)
print(analysis.summary)              # Overall risk assessment
print(analysis.concerns)             # Specific safety concerns
print(analysis.recommendations)      # Suggestions to reduce risk
print(analysis.recommended_risk)     # LLM's risk classification
print(analysis.chain_analysis)       # How actions interact

# Add context about your environment
analysis = analyzer.analyze_with_context(
    plan,
    context="This runs against a production database with 10M users"
)
```

## Framework Integrations

### OpenAI Function Calling

```python
from openai import OpenAI
from agent_preflight import Preflight
from agent_preflight.integrations.openai_hook import PreflightOpenAI

pf = Preflight()
hook = PreflightOpenAI(pf)

# Register tool executors
hook.register_tool("search_web", search_web_fn)
hook.register_tool("send_email", send_email_fn)

# Make your OpenAI call as normal
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    tools=[...],
)

# Capture tool calls from the response
hook.capture_from_response(response)

# Build and review the plan
plan = hook.build_plan(task="User request")
print(pf.format(plan))

# Execute only if safe
plan.approve()
plan.execute()
```

### Anthropic Tool Use

```python
import anthropic
from agent_preflight import Preflight
from agent_preflight.integrations.anthropic_hook import PreflightAnthropic

pf = Preflight()
hook = PreflightAnthropic(pf)

# Register tool executors
hook.register_tool("search_db", search_db_fn)

# Make your Anthropic call
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[...],
    tools=[...],
)

# Capture tool_use blocks
hook.capture_from_response(response)

plan = hook.build_plan(task="Claude task")
print(pf.format(plan))
```

### LangChain / LangGraph

```python
from agent_preflight import Preflight
from agent_preflight.integrations.langchain import PreflightCallbackHandler

pf = Preflight()
handler = PreflightCallbackHandler(pf)

# Use with any LangChain agent
agent.invoke(
    {"input": "Organize my tasks"},
    config={"callbacks": [handler.handler]},
)

plan = handler.build_plan(task="Organize tasks")
print(pf.format(plan))
```

## How It Works

```
Your Agent Code          Preflight Engine           Human Review
+--------------+    +----------------------+    +--------------+
|  @intercept  |--->|  1. Capture calls    |    |              |
|  tool calls  |    |  2. Classify risk    |    |  Review plan |
|              |    |  3. Build dep graph  |--->|  Run policies|
|  dry_run()   |    |  4. Render plan      |    |  Approve/Deny|
|              |    |  5. Check policies   |    |              |
+--------------+    |  6. Audit trail      |    +------+-------+
                    +----------------------+           |
                                                       v
                                              +--------------+
                                              |   Execute    |
                                              | (if approved)|
                                              +--------------+
```

1. **Intercept** - `@pf.intercept` wraps your tool functions
2. **Dry Run** - `pf.dry_run()` executes your agent logic but captures calls instead of running them
3. **Classify** - Each captured action is analyzed for risk, reversibility, and type
4. **Dependency Graph** - Data flow between actions is tracked, blind deletes flagged
5. **Render** - Human-readable plan with color-coded risk levels
6. **Policy Check** - Organizational rules evaluated against the plan
7. **Audit** - Plan recorded for compliance and debugging
8. **Approve** - Explicit approval gate before any real execution
9. **Execute** - Replays captured calls against real functions

Zero required dependencies. Works with any Python agent framework.

## CLI

```bash
preflight demo              # Interactive demo with policy checks
preflight check script.py   # Analyze a script's agent actions
preflight audit ./trail     # View audit history
preflight version           # Show version
```

## API Reference

### `Preflight(auto_classify=True, max_actions=100, cost_limit=None)`

Create a preflight engine.

### `@pf.intercept` / `@pf.intercept(cost=0.05, reversible=False)`

Decorator to register a tool for interception. Works with sync and async functions.

### `pf.dry_run(run_fn, task="")` / `await pf.async_dry_run(run_fn, task="")`

Execute in dry-run mode. All intercepted calls are captured, not executed. Returns a `Plan`.

### `Plan`

- `plan.actions` - List of captured `ActionCapture` objects
- `plan.overall_risk` - Highest risk level across all actions
- `plan.irreversible_count` - Number of irreversible actions
- `plan.warnings` - Auto-generated warnings
- `plan.dependency_graph` - `DependencyGraph` with execution order and cycle detection
- `plan.approve()` - Mark plan as approved
- `plan.execute()` / `await plan.async_execute()` - Execute all actions
- `plan.to_json()` / `plan.to_dict()` - Export

### `PolicyEngine`

- `engine.add(policy)` - Add a policy rule
- `engine.evaluate(plan)` - Returns `PolicyResult`

### `AuditLog(path, backend="json"|"sqlite")`

- `audit.record(plan, verdict, actor, ...)` - Persist a plan evaluation
- `audit.query(last_n, risk_level, actor, ...)` - Search history

### `SemanticAnalyzer(provider, model, llm_fn)`

- `analyzer.analyze(plan)` - LLM-powered risk analysis
- `analyzer.analyze_with_context(plan, context)` - Analysis with system context

### Custom Classifiers

```python
def my_classifier(action):
    if "prod" in str(action.args):
        action.risk_level = RiskLevel.CRITICAL
        action.risk_reasons.append("Production environment detected")
    return action

pf.add_classifier(my_classifier)
```

## Architecture

```
agent_preflight/
├── __init__.py              # Public API
├── core.py                  # Preflight engine (sync + async)
├── models.py                # ActionCapture, Plan, DependencyGraph
├── classifiers.py           # Heuristic risk classifiers
├── renderer.py              # Terraform-style terminal output
├── policy.py                # Policy engine with rule DSL
├── audit.py                 # Audit trail (JSON + SQLite)
├── semantic.py              # LLM-powered semantic analysis
├── cli.py                   # CLI entry point
└── integrations/
    ├── openai_hook.py       # OpenAI function calling
    ├── anthropic_hook.py    # Anthropic tool_use
    └── langchain.py         # LangChain callback handler
```

## Roadmap

- [ ] MCP (Model Context Protocol) tool wrapper
- [ ] Drift detection (compare plans over time)
- [ ] GitHub Action for CI/CD gating
- [ ] Web dashboard for team review
- [ ] Webhook notifications (Slack, Teams)
- [ ] Multi-agent fleet management

## License

MIT
