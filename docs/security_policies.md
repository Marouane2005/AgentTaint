# Security Policies

**Status:** Milestone 5 implemented; M9 default MCP path uses provenance-aware policy  
**Enforcement:** `StubPolicyAdapter` (M2 compatibility) + `ProvenanceAwarePolicy` (M5, **default** for `build_gateway_from_paths`). Cedar deferred.

---

## Decision outcomes

| Decision | Meaning |
|----------|---------|
| ALLOW | Forward tool call to backend |
| BLOCK | Refuse; return audit id |
| CONFIRM | Require human approval bound to `(tool, args_hash, agent_id)` |

---

## Design principles

1. Summarize/read does not authorize send/exec.  
2. Untrusted content cannot independently authorize externalization.  
3. UNKNOWN/PARTIAL on HIGH-risk → CONFIRM or BLOCK (`fail_closed_unknown_high`).  
4. USER-explicit recipients may ALLOW even if also seen in untrusted mail.  
5. Model text never overrides policy.  
6. Fail closed if provenance registry unavailable for HIGH-risk.  
7. **INFERRED evidence never silently becomes KNOWN and never alone ALLOWs HIGH-risk.**  
8. Bound confirmation is single-use, time-limited, and argument-exact.

---

## ProvenanceAwarePolicy rule order

1. HIGH + registry unavailable → `fail-closed-registry-unavailable` (BLOCK)  
2. Denylist tool → BLOCK  
3. Valid consumed confirmation → `confirmation-bound-allow`  
4. Static blocked recipient (unless USER-authorized value) → BLOCK  
5. HIGH + authority arg ∈ USER-authorized values → `allow-user-authorized-authority`  
6. HIGH + untrusted influence (explicit or inferred) without USER auth → BLOCK (or CONFIRM if configured)  
7. HIGH + UNKNOWN/PARTIAL → CONFIRM (or BLOCK if fail-closed)  
8. Other HIGH → CONFIRM  
9. LOW/MEDIUM → ALLOW  

YAML: `policies/provenance_policy.yaml` via `load_provenance_policy()`.

---

## Reconstruction in policy

Reconstruction may set `has_untrusted_influence` / `influence_inferred_only` and attach `ArgumentEvidence` with `evidence_type=INFERRED`.  
It must **not** populate `user_authorized_values` and must **not** flip spans to KNOWN.

See [security_integration.md](security_integration.md) for guarantees vs SDK requirements.

---

## Confirmation UX (MVP)

CLI (`interactive_confirm`): tool, redacted args, risk, policy id, lineage/explanation, args hash, expiry.  
Approval token is HMAC-bound; consume enforces exact arguments and single use.

---

## M9 notes

- Default MCP server wiring uses `ProvenanceAwarePolicy` (not stub allow-by-default).  
- Stub policy remains for explicit compatibility tests (`policies/stub_policy.yaml`).  
- Confirmation binding is enforced when `ConfirmationService` is injected; default FastMCP tool schemas still do **not** accept confirmation tokens — treat confirmation as SDK/gateway API until wired.
