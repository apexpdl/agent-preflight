# Threat Model

This document describes the threat model for Preflight, the execution governance layer for AI agents. It identifies threat actors, maps attack surfaces, defines trust boundaries, and documents mitigations using the STRIDE framework.

This is a living document. It is updated as the architecture evolves and new threat classes emerge.

## Overview

Preflight sits between AI agents and the tools they invoke. It intercepts every tool call, evaluates it against policy, scores its risk, optionally simulates it, and either permits or blocks execution. Every decision is cryptographically signed and recorded in a tamper-evident ledger.

The security objective is to ensure that no agent action reaches production without being verified, authorized, recorded, and attributable.

## Trust Boundaries

Preflight defines the following trust boundaries:

```
+--------------------------------------------------------------+
|                      Untrusted Zone                          |
|  [AI Agent]  [LLM Provider]  [External Tools]  [MCP Server] |
+---------------------------+----------------------------------+
                            |
                    Tool call interception
                            |
+---------------------------v----------------------------------+
|                   Preflight Governance Layer                 |
|  +---------------+  +-------------+  +-------------------+  |
|  | Policy Engine |  | Risk Scorer |  | Simulation Engine |  |
|  +---------------+  +-------------+  +-------------------+  |
|  +---------------+  +-------------+  +-------------------+  |
|  | Crypto Layer  |  |  Consensus  |  | Liability Ledger  |  |
|  +---------------+  +-------------+  +-------------------+  |
+---------------------------+----------------------------------+
                            |
                    Verified execution
                            |
+---------------------------v----------------------------------+
|                      Trusted Zone                            |
|  [Production Databases]  [APIs]  [File Systems]  [Networks]  |
+--------------------------------------------------------------+
```

**Boundary 1: Agent to Preflight.** Agent inputs (tool names, parameters, context) are untrusted. Preflight must validate and sanitize all inputs before policy evaluation.

**Boundary 2: Preflight to Tools.** After Preflight issues a PERMIT verdict and signs the Action Passport, the tool call is released to the real environment. Preflight trusts its own verdict but does not trust the tool's implementation.

**Boundary 3: Tenant to Tenant.** Each tenant operates in an isolated security context. No data, keys, policies, or ledger entries may cross tenant boundaries.

**Boundary 4: Operator to Preflight.** Operators authenticate to submit consensus votes. Preflight validates operator identity and authorization but does not control the operator's decision-making process.

## Threat Actors

### TA-1: Malicious Agent

An AI agent that has been prompt-injected, jailbroken, or is operating with a misaligned objective. The agent deliberately attempts to execute harmful actions (data exfiltration, destructive operations, unauthorized access).

**Capability:** Can craft arbitrary tool call requests. Can attempt to manipulate context or parameters to lower risk scores. Cannot directly access Preflight internals.

### TA-2: Compromised Tool

A tool in the agent's toolkit that has been modified by an attacker (supply chain compromise, malicious update, dependency confusion). The tool behaves normally for benign inputs but exfiltrates data or executes unauthorized side effects for specific triggers.

**Capability:** Full control over tool execution logic. Can return falsified results. Can attempt to communicate with external services. Cannot modify Preflight's interception layer.

### TA-3: Insider Threat

A developer, operator, or administrator with legitimate access to Preflight's configuration, policies, or infrastructure. Attempts to weaken security controls, approve unauthorized actions, or tamper with audit records.

**Capability:** May have access to policy definitions, operator credentials, or infrastructure. May attempt to modify policies to permit dangerous actions or suppress ledger entries.

### TA-4: Supply Chain Attacker

An attacker who compromises a dependency of Preflight itself (PyPI package, transitive dependency, build tooling). Injects malicious code that runs within Preflight's process.

**Capability:** Code execution within the Preflight process. Can potentially access key material, modify policy evaluation, or suppress ledger writes.

### TA-5: Network Attacker

An attacker with access to the network between Preflight components (agent, governance layer, tools, consensus endpoints). Attempts to intercept, modify, or replay messages.

**Capability:** Can observe and modify network traffic if encryption is not enforced. Can attempt replay attacks with captured Action Passports.

## STRIDE Threat Analysis

### Spoofing

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| S-1 | Agent impersonates another agent to inherit its permissions | Agent identity at governance boundary | Agent identity is bound to the cryptographic key pair used to sign requests. Each agent has a unique key pair. Identity cannot be forged without the private key. | Key compromise. Mitigated by key rotation and revocation support. |
| S-2 | Operator impersonation during consensus voting | Consensus layer | Each operator vote is individually signed with the operator's key pair. The consensus layer verifies signatures before counting votes. | Operator key compromise. Organizations should use hardware-backed keys for production deployments. |
| S-3 | Forged Action Passport presented to bypass governance | Tool execution boundary | Action Passports are Ed25519-signed. Tools can independently verify the passport signature against Preflight's public key before executing. | Tools that do not verify passports. Verification is opt-in at the tool layer. |

### Tampering

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| T-1 | Modification of a historical ledger record to hide a dangerous action | Liability ledger | Chain hashing: `chain_hash[n] = SHA-256(chain_hash[n-1] \|\| record_data)`. Any modification breaks the hash chain and is detectable during verification. Ledger is append-only at the schema level. | Attacker with direct database access could rewrite the entire chain. Mitigated by periodic external checkpointing and export to immutable storage. |
| T-2 | Tampering with policy definitions to permit dangerous actions | Policy engine | Policy changes should be managed through version control with code review. Preflight records the policy hash used for each verdict in the ledger. Policy drift is detectable by comparing recorded hashes against the policy repository. | Insider with commit access to the policy repository. Mitigated by branch protection and multi-party review. |
| T-3 | Modification of tool call parameters after risk scoring but before execution | Execution envelope | The Deterministic Execution Envelope (DEE) binds tool name, parameters, and risk score into a signed artifact. Any modification invalidates the signature. | Time-of-check-to-time-of-use (TOCTOU) if verification and execution are not atomic. The DEE signature should be verified immediately before tool dispatch. |
| T-4 | Tampering with simulation results to misrepresent risk | Simulation engine | Simulation inputs and outputs are recorded in the ledger. Deterministic replay allows re-execution of any simulation with the same seed to verify results. | Non-deterministic tool behavior in sandbox mode. |

### Repudiation

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| R-1 | Agent denies having requested a destructive action | Audit trail | Every action request is signed by the agent's key pair and recorded in the liability ledger with the agent's signature, the tool call parameters, and a timestamp. | HMAC-SHA256 fallback mode does not provide non-repudiation (symmetric key). Deployments requiring non-repudiation must use the Ed25519 backend. |
| R-2 | Operator denies having approved a high-risk action | Consensus records | Each consensus vote is individually signed and recorded. The full vote history (including timestamps, voter identity, and vote content) is persisted in the ledger. | None when Ed25519 is used. |

### Information Disclosure

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| I-1 | Key material exposed through logs or error messages | Cryptographic keys | Private keys are never serialized to JSON, included in log output, or returned through the API. Key material is held in memory only. | Memory dump or core dump could expose key material. Deployments should disable core dumps in production. |
| I-2 | Cross-tenant data leakage through shared infrastructure | Tenant data | Tenant isolation is enforced at the TrustKernel level. Each tenant has separate key material, policy namespaces, and ledger partitions. Queries are scoped to the authenticated tenant context. | Bugs in tenant isolation logic. Mitigated by integration tests that verify cross-tenant access is denied. |
| I-3 | Ledger contents expose sensitive tool call parameters | Audit records | Ledger records store tool names and parameter metadata. Sensitive parameter values (credentials, PII) should be redacted by the tool integration before reaching Preflight. | Tool integrations that do not redact sensitive values. This is the tool author's responsibility. |

### Denial of Service

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| D-1 | Flood of tool call requests overwhelms the governance layer, causing fail-open | Policy engine | Preflight defaults to fail-closed: if the governance layer is unavailable or overloaded, actions are blocked, not permitted. Rate limiting is configurable per tenant. | Legitimate actions are also blocked during overload. This is an availability trade-off, not a security gap. |
| D-2 | Large number of consensus requests exhausts operator attention | Consensus layer | Consensus requests have configurable expiry (default: 30 minutes). Expired requests are automatically denied. Risk thresholds for consensus can be tuned to reduce noise. | Alert fatigue may cause operators to approve without careful review. This is an organizational risk. |
| D-3 | Ledger storage exhaustion prevents new records from being written | Liability ledger | Monitoring and alerting on ledger size. Ledger compaction and archival to external storage. Preflight blocks execution if the ledger write fails (fail-closed). | Disk exhaustion on the host. Standard infrastructure monitoring applies. |

### Elevation of Privilege

| ID | Threat | Target | Mitigation | Residual Risk |
|----|--------|--------|------------|---------------|
| E-1 | Agent manipulates tool call parameters to escalate its effective permissions | RBAC boundary | Policy evaluation considers the full parameter set, not just the tool name. Destructive patterns (e.g., `DROP TABLE`, `rm -rf`, wildcard deletions) are detected by the risk scorer regardless of the agent's stated intent. | Novel parameter patterns not covered by existing risk classifiers. Mitigated by continuous classifier updates and the simulation engine. |
| E-2 | MCP message injection to bypass risk scoring | MCP integration layer | MCP messages are parsed and validated before policy evaluation. Tool call parameters extracted from MCP messages are treated as untrusted input. The MCP integration does not grant any implicit trust based on the message source. | Novel MCP injection techniques. The MCP specification is evolving, and new message types may introduce new attack surface. |
| E-3 | Exploiting the HMAC-SHA256 fallback to forge signatures | Cryptographic layer | The HMAC fallback uses a 256-bit secret key generated from a cryptographically secure random source. The key is never transmitted or exposed through the API. However, HMAC is a symmetric primitive -- anyone with access to the key can sign. | Insider with access to the HMAC key can forge signatures. The Ed25519 backend eliminates this risk through asymmetric cryptography. The HMAC fallback should not be used in deployments where non-repudiation is required. |

## Attack Surface Map

### Tool Call Interception

**Surface:** The interface where agent tool calls enter Preflight.

**Attacks:** Malformed tool call parameters designed to crash the parser. Oversized payloads. Encoding tricks (Unicode normalization, homoglyph attacks) to bypass keyword-based risk detection.

**Mitigations:** Input validation and size limits. Canonical normalization before risk scoring. Fail-closed on parse errors.

### Policy Bypass

**Surface:** The policy engine that evaluates whether an action is permitted.

**Attacks:** Crafting tool calls that technically satisfy policy but achieve a prohibited outcome (semantic bypass). Splitting a dangerous action into multiple benign-looking steps that individually pass policy but collectively cause harm.

**Mitigations:** Semantic risk scoring that evaluates intent, not just syntax. Session-level context tracking to detect multi-step attack chains. Monte Carlo simulation to project probable outcomes. Cumulative risk scoring across action sequences.

### Passport Forgery

**Surface:** The Action Passport (signed DEE) that authorizes tool execution.

**Attacks:** Forging a passport to execute a tool call without governance. Replaying a previously valid passport for a different action.

**Mitigations:** Ed25519 signatures are computationally infeasible to forge. Passports include a unique action ID, timestamp, and the specific tool call parameters -- replaying a passport for a different action invalidates the signature. Passport expiry prevents indefinite replay.

### Ledger Tampering

**Surface:** The append-only liability ledger.

**Attacks:** Deleting records to hide evidence of a dangerous action. Modifying records to change the recorded verdict or risk score. Inserting fabricated records.

**Mitigations:** SHA-256 chain hashing makes any modification detectable. Append-only schema prevents deletion through the Preflight API. Periodic external checkpointing to immutable storage provides an independent verification baseline.

### MCP Injection

**Surface:** The Model Context Protocol integration that receives structured messages from agent frameworks.

**Attacks:** Injecting tool calls through MCP message fields that are not subject to governance. Manipulating MCP metadata to influence risk scoring. Exploiting differences between how MCP messages are parsed by the agent framework and by Preflight.

**Mitigations:** All tool calls extracted from MCP messages pass through the same governance pipeline as direct calls. MCP metadata is not trusted for risk scoring decisions. Preflight parses MCP messages independently rather than relying on the agent framework's interpretation.

## What Preflight Does NOT Protect Against

Preflight is an execution governance layer. It is not a comprehensive security solution. The following threats are explicitly out of scope:

1. **Prompt injection and jailbreaking.** Preflight governs what agents do, not what they think. If an agent is manipulated into wanting to perform a harmful action, Preflight will evaluate that action against policy and may block it -- but Preflight does not inspect or secure the LLM inference process itself.

2. **Malicious tool implementations.** Preflight verifies that a tool call is authorized and records its execution. It does not sandbox or inspect the tool's internal logic. A tool that behaves maliciously (e.g., exfiltrates data while appearing to perform a benign operation) is outside Preflight's control. The Mirror World sandbox can detect observable side effects but cannot guarantee complete isolation for arbitrary tool code.

3. **Compromise of the host system.** If an attacker gains root access to the machine running Preflight, all bets are off. Key material, policy files, and the ledger database are accessible to a root-level attacker. Preflight assumes the host operating system and runtime are trustworthy.

4. **Social engineering of operators.** Preflight can require M-of-N operator approval for high-risk actions, but it cannot prevent operators from being tricked, coerced, or bribed into approving malicious actions. Operator security is an organizational responsibility.

5. **Data-level attacks.** Preflight evaluates tool calls at the API level. It does not inspect the data returned by tools for correctness, poisoning, or manipulation. A tool that returns falsified data (e.g., a compromised database returning incorrect account balances) is not detectable by Preflight.

6. **Side-channel attacks.** Timing side channels in cryptographic operations, cache-based attacks, and other hardware-level side channels are not addressed. The `cryptography` library used for Ed25519 provides constant-time operations where possible, but Preflight does not make additional side-channel guarantees.

7. **Availability of external dependencies.** Preflight fails closed when it cannot reach its own components, but it does not guarantee the availability of external tools, APIs, or LLM providers.

## Assumptions

This threat model assumes:

- The host operating system and Python runtime are not compromised.
- The `cryptography` library (when used) correctly implements Ed25519 and SHA-256.
- Cryptographic random number generation (`secrets` module, `/dev/urandom`) is secure.
- Network transport between distributed Preflight components uses TLS 1.2 or higher (deployment responsibility).
- Operators who participate in consensus are authenticated through an external identity provider.
- Policy definitions are managed through a version-controlled repository with appropriate access controls.

## Revision History

| Date | Change |
|------|--------|
| 2025-06-01 | Initial threat model |
| 2025-09-01 | Added MCP injection surface, updated STRIDE table |
| 2026-03-10 | Added supply chain threat actor, expanded simulation threats |
