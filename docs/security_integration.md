# Security Integration (Milestone 5)

**Status:** Implemented (local MVP)  
**Cedar:** default engine (`CedarProvenancePolicy`); `ProvenanceAwarePolicy` is the parity-tested reference.

---

## What the system guarantees

When components share a secret, a provenance registry, and cooperate via the AgentTaint SDK + MCP gateway:

| Guarantee | Mechanism |
|-----------|-----------|
| Tampered cross-agent envelopes are rejected | HMAC-SHA256 over canonical envelope fields |
| Replayed envelopes are rejected | Single-use nonce store |
| Stale envelopes are rejected | `max_age` + clock-skew window |
| Claimed parent spans must exist | Registry lookup before seal/accept |
| User confirmation binds to exact `(tool, args_hash, agent_id)` | HMAC approval token + consume-once |
| Modified arguments after approval fail | `arguments_hash` mismatch → fail closed |
| Expired / replayed confirmations fail | TTL + `CONSUMED` status |
| INFERRED reconstruction never becomes KNOWN | Evidence type + status invariants; policy never ALLOWs HIGH on inference alone |
| Missing registry on HIGH-risk fails closed | `registry_available=False` → BLOCK |
| Tool results are labeled after ALLOW | Gateway always records a provenance span + audit row |

---

## What requires SDK instrumentation

Without SDK / gateway cooperation, AgentTaint **cannot** claim:

1. **Complete transformation lineage** after uninstrumented LLM calls (gaps → PARTIAL/UNKNOWN).
2. **Authenticated multi-agent handoff** — plaintext agent messages without envelopes have no integrity or agent-identity binding.
3. **Argument causation** — reconstruction supplies INFERRED influence signals only.
4. **Authorization from content** — only explicit USER-grounded values (or a bound confirmation) authorize HIGH-risk authority arguments.
5. **Protection against a compromised TCB** (proxy, registry DB, shared HMAC secret, policy YAML).

---

## Components

```
AgentTaintContext  → summarize / rewrite / remember / recall / mark_untracked
                   → delegate() seals ProvenanceEnvelope
                   → accept() verifies + transfer_to_agent

ConfirmationService → request / approve|deny / consume (bound, single-use)

SecurityGateway     → risk → (optional reconstruct) → PolicyContext → policy
                    → CONFIRM creates binder record; ALLOW forwards + labels
```

Policy file: `policies/provenance_policy.yaml`  
Loader: `load_provenance_policy()`

---

## Confirmation UX (CLI)

`interactive_confirm()` prints tool, redacted args, risk, policy id, args hash, expiry.  
Approval is useless without presenting the same arguments again at consume time.

---

## Non-goals (still)

- Dashboard / metrics UI  
- Cedar policy backend  
- Mutual TLS / per-agent asymmetric keys (shared HMAC is local-dev strength)  
- Benchmark suite (Milestone 6 — awaiting approval)
