# Action Passport v1.0 Specification

## Overview

An Action Passport is a cryptographically signed, tamper-proof audit artifact that records the complete lifecycle of a governed AI agent action. Every action that passes through the Preflight pipeline receives a passport, regardless of whether the action was allowed, warned, or blocked.

Passports are designed for:

- **Regulatory compliance** -- court-admissible evidence of governance decisions
- **Forensic analysis** -- reconstruct exactly what happened, when, and why
- **Audit trails** -- prove that governance was applied and what the outcome was
- **Cross-organization verification** -- independent parties can verify passport authenticity

## Schema

The full JSON Schema is at [specs/action-passport-v1.0.json](../specs/action-passport-v1.0.json).

## Structure

### Required Fields

| Field | Type | Description |
|---|---|---|
| `passport_version` | string | Always `"1.0"` |
| `passport_id` | UUID | Globally unique passport identifier |
| `timestamp` | ISO 8601 | UTC timestamp of passport creation |
| `agent` | object | Agent identity (agent_id, framework, model, session) |
| `action` | object | Tool name, action type, arguments, intent, targets |
| `risk_assessment` | object | Composite score, component scores, simulation results |
| `verdict` | object | Decision (allow/warn/block/escalate), reason, policy refs |
| `execution` | object | Pre/post state hashes, state diff, pipeline duration |
| `signatures` | object | Ed25519 or HMAC-SHA256 signatures with key references |
| `chain` | object | Previous hash, record hash, sequence number |

### Signatures

Passports support two signing algorithms:

- **Ed25519** (recommended) -- asymmetric signing with public key distribution for independent verification
- **HMAC-SHA256** (fallback) -- symmetric signing for zero-dependency environments

Dual signatures are applied:

1. **Agent signature** -- signed by the key associated with the agent identity
2. **Policy signature** -- signed by the Preflight policy engine key

When M-of-N consensus is required, an additional **operator signature** is included with each approving operator's vote.

### Chain Hashing

Every passport includes a `chain` object linking it to the previous passport in the ledger:

- `previous_hash` -- SHA-256 hash of the previous passport
- `record_hash` -- SHA-256 hash of this passport's content (excluding chain fields)
- `sequence_number` -- monotonically increasing counter

This creates an append-only, tamper-evident chain. Any modification to a historical record breaks the chain hash, making tampering detectable.

## Verification

To verify a passport:

1. Recompute `record_hash` from the passport content
2. Verify the Ed25519/HMAC-SHA256 signatures against the referenced public keys
3. Verify `previous_hash` matches the `record_hash` of the preceding passport
4. Verify `sequence_number` is exactly one greater than the preceding passport

```python
from trust_kernel.crypto import CryptoProvider

crypto = CryptoProvider()
is_valid = crypto.verify_receipt(passport)
```

## Storage

Passports are stored in the liability ledger, an append-only data store. Supported backends:

- SQLite (default, zero-config)
- PostgreSQL (planned)
- S3-compatible object storage (planned)

## Export

Passports can be exported in JSON or JSONL format for external audit tools:

```
GET /ledger/export/json
GET /ledger/export/jsonl
```

## Extensibility

The `metadata.extensions` field allows vendor-specific data to be attached to any passport without modifying the core schema.
