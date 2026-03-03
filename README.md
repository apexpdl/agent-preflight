# agent-preflight

**Preview what your AI agent will do before it does it.**

The `terraform plan` for AI agents. Open-source middleware that intercepts tool calls, classifies risk, and shows a human-readable execution plan before anything touches the real world.

```
================================================================
  PREFLIGHT PLAN    5 action(s)
  Send Q3 report to Sarah at Acme
================================================================

  WARNING: 3 irreversible action(s) in plan

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

## Features

**Action Classification** - Automatically detects risk level, reversibility, and action type from function names and arguments. `send_email` -> IRREVERSIBLE. `get_users` -> READ/LOW. `DROP TABLE` in args -> CRITICAL.

**Loop Detection** - Flags when the same tool is called 3+ times, catching runaway agent loops before they become $47K bills.

**Cost Tracking** - Attach cost estimates to tools, set budget limits. Preflight warns when a plan exceeds your threshold.

**SQL Danger Detection** - Catches `DROP TABLE`, `DELETE` without `WHERE`, `TRUNCATE`, and other destructive SQL patterns in arguments.

**Approve/Execute Flow** - Plans must be explicitly approved before execution. No accidental runs.

**JSON Export** - `plan.to_json()` for programmatic use, CI/CD integration, and audit trails.

**Context Manager** - Record mode for capturing actions in existing code:

```python
with pf.recording(task="nightly cleanup") as rec:
    cleanup_old_files()
    archive_logs()

print(pf.format(rec.plan))
```

**Custom Classifiers** - Add your own classification logic:

```python
def my_classifier(action):
    if "prod" in str(action.args):
        action.risk_level = RiskLevel.CRITICAL
        action.risk_reasons.append("Production environment detected")
    return action

pf.add_classifier(my_classifier)
```

## How It Works

1. **Intercept** - `@pf.intercept` wraps your tool functions
2. **Dry Run** - `pf.dry_run()` executes your agent logic but captures calls instead of running them
3. **Classify** - Each captured action is analyzed for risk, reversibility, and type
4. **Render** - Human-readable plan with color-coded risk levels
5. **Approve** - Explicit approval gate before any real execution
6. **Execute** - Replays captured calls against real functions

Zero dependencies. Works with any Python agent framework.

## Demo

```bash
preflight demo
```

## API

### `Preflight(auto_classify=True, max_actions=100, cost_limit=None)`

Create a preflight engine.

- `auto_classify` - Run built-in classifiers on captured actions
- `max_actions` - Safety cap on captured actions per dry run
- `cost_limit` - Warn if total estimated cost exceeds this

### `@pf.intercept` / `@pf.intercept(cost=0.05, reversible=False)`

Decorator to register a tool for interception. Supports manual metadata overrides.

### `pf.dry_run(run_fn, task="")`

Execute `run_fn` in dry-run mode. All intercepted calls are captured, not executed. Returns a `Plan`.

### `Plan`

- `plan.actions` - List of captured `ActionCapture` objects
- `plan.overall_risk` - Highest risk level across all actions
- `plan.irreversible_count` - Number of irreversible actions
- `plan.warnings` - Auto-generated warnings (loops, cost, irreversible actions)
- `plan.approve()` - Mark plan as approved
- `plan.execute()` - Execute all actions (must approve first)
- `plan.to_json()` - Export as JSON
- `plan.to_dict()` - Export as dict

### `pf.format(plan, color=True)`

Render plan as terminal output with ANSI colors.

## Roadmap

- [ ] LangChain/LangGraph callback adapter
- [ ] MCP tool wrapper
- [ ] Drift detection (compare plans over time)
- [ ] GitHub Action for CI/CD
- [ ] Web dashboard

## License

MIT
