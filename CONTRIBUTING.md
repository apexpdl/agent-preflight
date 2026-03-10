# Contributing to Preflight

Preflight is the execution governance layer for AI agents. Every contribution to this project directly impacts the safety boundary between autonomous AI systems and the real world. We treat that responsibility seriously, and we expect contributors to do the same.

We welcome contributions from security engineers, infrastructure developers, AI practitioners, and anyone committed to making autonomous agents safer. Whether you are fixing a bug, adding a simulation plugin, or proposing a new pipeline stage, your work matters.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Branch and Pull Request Workflow](#branch-and-pull-request-workflow)
- [Coding Standards](#coding-standards)
- [Adding New Components](#adding-new-components)
- [Test Requirements](#test-requirements)
- [Design Partner Program](#design-partner-program)

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

1. Fork the repository and clone your fork:

```bash
git clone https://github.com/<your-username>/agent-preflight.git
cd agent-preflight
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

This installs all development dependencies including `pytest`, `pytest-asyncio`, and `pydantic`.

4. For working on specific integrations, install the relevant extras:

```bash
pip install -e ".[dev,openai,anthropic,langchain,server,yaml]"
# or install everything:
pip install -e ".[dev,all]"
```

5. Verify your setup:

```bash
pytest
```

All tests should pass before you begin development.

---

## Branch and Pull Request Workflow

1. **Create a feature branch** from `main`:

```bash
git checkout -b feat/your-feature-name
```

Use a descriptive branch prefix:
- `feat/` for new features and capabilities
- `fix/` for bug fixes
- `refactor/` for code restructuring
- `test/` for test additions or improvements
- `docs/` for documentation changes

2. **Make focused, atomic commits.** Each commit should represent a single logical change. Write clear commit messages that explain the "why," not just the "what."

3. **Push your branch** to your fork:

```bash
git push origin feat/your-feature-name
```

4. **Open a Pull Request** against `main` on the upstream repository.

5. **PR requirements:**
   - A clear description of the change and its motivation
   - All existing tests pass
   - New tests covering the added or changed functionality
   - No regressions in performance-sensitive paths (risk engine, pipeline stages)
   - Type hints on all public interfaces

6. **Review process:** All PRs require at least one maintainer review. Security-sensitive changes (crypto, policy engine, trust kernel) require two reviews.

---

## Coding Standards

Preflight is infrastructure-grade software. The codebase enforces strict standards to maintain reliability and auditability.

### Type Hints

All functions, methods, and module-level variables must include type annotations. Use `typing` module constructs where needed. No `Any` types in public interfaces without documented justification.

```python
async def evaluate_action(
    self,
    action: ActionRequest,
    context: ExecutionContext,
) -> PipelineResult:
    ...
```

### Pydantic Models

All data structures that cross module boundaries must be Pydantic `BaseModel` subclasses. This ensures runtime validation, serialization, and schema generation.

```python
from pydantic import BaseModel, Field

class RiskAssessment(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    verdict: Verdict
```

### Async-First

New code should be async by default. The project uses `asyncio` throughout the pipeline. Synchronous wrappers may be provided for convenience, but the primary implementation must be async.

### General Conventions

- Follow PEP 8 and PEP 257 for code style and docstrings.
- Use descriptive variable and function names. Avoid abbreviations.
- Keep functions focused. A function should do one thing.
- No print statements in library code. Use structured logging.
- All cryptographic operations must use constant-time comparison functions.
- Never silently swallow exceptions in safety-critical paths.

---

## Adding New Components

### Pipeline Stages

The Preflight pipeline (`agent_preflight/atf/`) processes actions through ordered stages. To add a new stage:

1. Create a new module in `agent_preflight/atf/` implementing the stage logic.
2. Define input and output models as Pydantic `BaseModel` subclasses.
3. Implement the stage as an async function or class with a well-defined interface.
4. Register the stage in the pipeline orchestrator.
5. Write unit tests covering normal operation, edge cases, and failure modes.
6. Document the stage's purpose, inputs, outputs, and failure behavior.

### Simulation Plugins

The Monte Carlo simulation engine (`agent_preflight/atf/simulation.py`) supports domain-specific plugins in `agent_preflight/atf/plugins/`. To add a new simulation plugin:

1. Create a new module in `agent_preflight/atf/plugins/`.
2. Implement the plugin interface with perturbation logic specific to the domain (e.g., network failures, rate limiting, resource exhaustion).
3. Define the probability distributions and failure scenarios the plugin models.
4. Ensure the plugin is stateless and thread-safe.
5. Add tests that validate the statistical properties of the simulation output.

### Integrations

Framework integrations live in `agent_preflight/integrations/`. To add support for a new agent framework:

1. Create a new module in `agent_preflight/integrations/`.
2. Implement the hook or wrapper that intercepts tool calls in the target framework.
3. Convert framework-specific action representations into Preflight's internal `ActionRequest` model.
4. If the integration requires additional dependencies, add them as an optional dependency group in `pyproject.toml`.
5. Add the integration to the auto-detection logic in `agent_preflight/auto.py`.
6. Write integration tests that verify correct interception and governance behavior.
7. Add a usage example to the README.

### Trust Kernel Components

Enterprise features in `trust_kernel/` require elevated review standards. Changes to cryptographic signing, the liability ledger, consensus mechanisms, or multi-tenant isolation require:

- Two maintainer approvals
- Explicit security analysis in the PR description
- No reduction in existing test coverage

---

## Test Requirements

All contributions must include tests. The project uses `pytest` with `pytest-asyncio` for async test support.

### Running Tests

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_risk_engine.py

# Run a specific test
pytest tests/test_risk_engine.py::test_destructive_action_scoring
```

### Test Standards

- **Unit tests** for all new functions and classes.
- **Edge case coverage** for boundary conditions (zero values, empty inputs, maximum values).
- **Failure mode tests** verifying that errors are handled correctly and safely (fail-closed, not fail-open).
- **Async tests** using `pytest-asyncio` for all async code paths.
- **No mocking of security-critical logic.** Crypto operations, policy evaluation, and risk scoring must be tested against real implementations.
- **Performance-sensitive tests** should assert timing constraints where applicable (e.g., risk engine under 1ms).

### Test Organization

Tests mirror the source tree structure:

```
tests/
  test_core.py
  test_risk_engine.py
  test_simulation.py
  test_policy.py
  test_integrations/
    test_openai_hook.py
    test_anthropic_hook.py
    ...
  test_trust_kernel/
    test_crypto.py
    test_ledger.py
    ...
```

---

## Design Partner Program

Preflight offers a Design Partner Program for organizations deploying AI agents in production environments who want to influence the project's roadmap. Design partners receive:

- Direct input on feature prioritization and API design
- Early access to enterprise capabilities before public release
- Dedicated support channels with the maintainer team
- Collaborative development of domain-specific simulation plugins and policy templates

If your organization is operating AI agents at scale and wants to help shape the governance layer that protects your infrastructure, open an issue with the title "Design Partner Program Inquiry" or contact the maintainers directly through the repository.

---

## Questions

If you are unsure about any aspect of contributing, open an issue. We would rather answer questions early than review a PR that heads in the wrong direction.

Thank you for helping make AI agents safer.
