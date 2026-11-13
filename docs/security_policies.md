# Security Policies

**Status:** Design  
**Enforcement:** Deterministic `PolicyAdapter` for MVP; Cedar planned as alternate backend.

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
3. UNKNOWN/PARTIAL on HIGH-risk → CONFIRM or BLOCK (config).  
4. USER-explicit recipients may ALLOW even if also seen in untrusted mail.  
5. Model text never overrides policy.  
6. Fail closed if provenance service unavailable for HIGH-risk.

---

## Initial policy set (conceptual)

1. `allow-low-risk`  
2. `block-untrusted-external-recipient`  
3. `confirm-unknown-high-risk`  
4. `allow-user-authorized-recipient`  
5. `block-shell-without-user-command` (when shell enabled)

Exact YAML lives in `policies/` once Milestone 5 lands. Until then, do not claim production policy coverage.

---

## Confirmation UX (MVP)

CLI shows: tool, redacted args, risk, untrusted source ids, policy id, lineage summary.  
Approval is single-use and time-limited.
