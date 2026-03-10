# Security Policy

Preflight is execution governance infrastructure for AI agents. Security is not a feature of this project -- it is the entire point. We treat every vulnerability report with the urgency it deserves.

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.0.x   | Yes                |
| 1.x.x   | Critical fixes only|
| < 1.0   | No                 |

Security patches are backported to the latest minor release of each supported major version. Users on unsupported versions should upgrade immediately.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Send vulnerability reports to:

```
security@preflight.dev
```

Include the following in your report:

- Description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof of concept
- Affected versions (if known)
- Whether you believe the issue is actively exploited

We will acknowledge receipt within 48 hours and provide an initial assessment within 5 business days. We aim to release a fix within 14 days of confirmed critical vulnerabilities, and within 30 days for lower-severity issues.

If you have not received a response within 48 hours, follow up at the same address with "URGENT" in the subject line.

We do not currently operate a bug bounty program.

## Security Model

Preflight operates as an execution governance layer between AI agents and the tools they invoke. The security model is built on four principles:

1. **Verify before execution.** Every tool call is intercepted, risk-scored, and validated against policy before it reaches the real world.
2. **Cryptographic non-repudiation.** Every action is signed and recorded in a tamper-evident ledger. No action can be denied or retroactively altered.
3. **Least privilege by default.** Agents operate in tenant-isolated contexts with explicit RBAC grants. No implicit permissions exist.
4. **Defense in depth.** Multiple independent layers (policy engine, risk scoring, simulation, consensus, cryptographic verification) must all agree before a high-risk action proceeds.

### Cryptographic Model

Preflight uses a layered cryptographic architecture:

**Action Passports (Ed25519)**

Every action that passes through Preflight receives a cryptographically signed Action Passport -- a Deterministic Execution Envelope (DEE) that binds the agent identity, tool call parameters, risk assessment, policy verdict, and pre-execution state hash into a single signed artifact.

- **Primary:** Ed25519 asymmetric signatures via the `cryptography` library. Ed25519 provides 128-bit security, deterministic signatures (no nonce reuse risk), and high throughput (~60,000 sign/verify operations per second on commodity hardware).
- **Fallback:** HMAC-SHA256 deterministic signatures for zero-dependency operation. The HMAC fallback provides integrity and authenticity but does not provide non-repudiation, since the signing key is symmetric. Deployments requiring non-repudiation must use the Ed25519 backend.

Key pairs support generation, rotation, revocation, and public key export for independent third-party verification.

**Liability Ledger (SHA-256 Chain Hash)**

The append-only liability ledger stores every action record with a chain hash linking each entry to its predecessor. This creates a tamper-evident audit trail:

```
chain_hash[n] = SHA-256(chain_hash[n-1] || record_id || action_data || timestamp)
```

Any modification to a historical record breaks the chain and is detectable during verification. The ledger is backed by SQLite with indexed queries by agent, timestamp, verdict, and risk score.

**Operator Consensus Signatures**

High-risk actions requiring M-of-N operator approval collect individually signed votes. Each vote is cryptographically bound to the consensus request ID, the voter identity, and a timestamp. The consensus threshold is configurable per policy.

**Envelope Integrity**

HMAC-SHA256 is used for envelope-level integrity checks on serialized execution state, ensuring that execution envelopes are not modified in transit between Preflight components.

### Multi-Tenant Isolation

Preflight enforces tenant isolation at the kernel level. Each tenant operates in a separate security context with:

- Isolated policy namespaces
- Separate cryptographic key material
- Independent ledger partitions
- Role-based access control (RBAC) for operators, agents, and auditors

Cross-tenant access is not possible through the Preflight API. Tenant boundaries are enforced in the TrustKernel, not at the application layer.

### Simulation and Sandbox Execution

Before high-risk actions reach production, Preflight can execute them in a Mirror World sandbox -- an isolated replica environment. The Monte Carlo simulation engine runs stochastic risk projections to estimate the probability distribution of outcomes. Simulation results are recorded in the ledger alongside the real execution record.

Sandbox execution is designed to be side-effect-free. However, Preflight does not guarantee that all tool implementations are safe to execute in sandbox mode. Tool authors are responsible for ensuring their tools respect the sandbox flag.

## Threat Model

A comprehensive threat model is maintained at [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). It covers:

- Threat actor profiles (malicious agents, compromised tools, insider threats, supply chain attacks)
- Attack surface mapping (tool calls, policy bypass, passport forgery, ledger tampering, MCP injection)
- Trust boundary definitions
- STRIDE-based threat classification
- Mitigations and residual risks

## Scope

### In Scope

The following are considered valid security vulnerabilities:

- Bypass of the policy engine allowing unauthorized tool execution
- Forgery or tampering of Action Passports or Deterministic Execution Envelopes
- Tampering with or truncation of the liability ledger without detection
- Bypass of M-of-N operator consensus requirements
- Cross-tenant data access or privilege escalation
- Cryptographic key material exposure through the API or logs
- Injection attacks through tool call parameters that manipulate Preflight's own behavior
- MCP (Model Context Protocol) message injection that bypasses risk scoring
- Bypass of the sandbox/Mirror World isolation boundary
- Denial of service against the governance layer that causes actions to pass unverified

### Out of Scope

The following are not considered Preflight security vulnerabilities:

- Vulnerabilities in the AI models themselves (prompt injection, jailbreaking) -- Preflight governs execution, not inference
- Vulnerabilities in third-party tools that Preflight intercepts -- report these to the tool maintainers
- Social engineering of human operators during consensus approval
- Attacks requiring physical access to the host machine
- Attacks requiring pre-existing root/administrator access on the host
- Performance degradation that does not bypass security controls
- Vulnerabilities in dependencies -- report these upstream; we will update promptly

## Secure Development Practices

- All cryptographic operations use well-established primitives (Ed25519, SHA-256, HMAC-SHA256). No custom cryptography.
- Secrets and key material are never logged, serialized to JSON, or included in error messages.
- The ledger schema enforces append-only semantics at the database level.
- Policy evaluation is deterministic -- the same input always produces the same verdict.
- Deterministic replay ensures that any historical action can be re-evaluated against current or historical policy.

## Disclosure Policy

We follow coordinated disclosure. Once a fix is available, we will:

1. Release the patched version to PyPI.
2. Publish a security advisory on the GitHub repository.
3. Credit the reporter (unless they request anonymity).

We request that reporters allow up to 90 days before public disclosure to give users time to upgrade.
