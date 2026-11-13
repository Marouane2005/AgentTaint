# Threat Model — AgentTaint

**Status:** Living — updated M9 independent review  
**Date:** 2026-11-13  
**Scope:** AI agents using tools via MCP, with optional multi-agent delegation, under AgentTaint SDK + MCP security proxy.

---

## 1. Assets to protect

| Asset | Examples | Why it matters |
|-------|----------|----------------|
| Confidential data | Files, emails, DB rows, credentials in tool outputs | Exfiltration via `email.send`, `http.post`, chat |
| Action integrity | Shell commands, file writes, payments, message sends | Unauthorized side effects |
| User intent | Explicit user instructions and confirmations | Must not be overridden by untrusted content |
| Security policy & trust registry | Risk tiers, Cedar policies, allowlists | Compromise → complete bypass |
| Provenance integrity | Spans, edges, hashes, signatures | Forged lineage → false ALLOW |
| Audit trail | ToolCallDecision records | Tampering hides attacks |

---

## 2. Principals and trust boundaries

```
┌─────────────────────────────────────────────────────────────┐
│ TRUSTED COMPUTING BASE (TCB)                                │
│  - AgentTaint MCP Proxy                                     │
│  - Provenance Service (registry + graph store)              │
│  - Policy Engine + Trust Registry                           │
│  - Confirmation channel (human / CLI)                       │
│  - Mock / sandboxed MCP tool backends (demo)                │
└─────────────────────────────────────────────────────────────┘
          ▲ authn                    ▲ authn
          │                          │
┌─────────┴──────────┐    ┌──────────┴──────────┐
│ Agent runtime + SDK│    │ Peer AgentTaint agent│
│ (partially trusted)│    │ (cooperating, verified│
│                    │    │  metadata only)       │
└─────────┬──────────┘    └──────────┬──────────┘
          │                          │
          ▼ untrusted content        ▼
┌─────────────────────────────────────────────────────────────┐
│ UNTRUSTED WORLD                                             │
│  Emails, web pages, GitHub issues, tool payloads,           │
│  third-party MCP servers, non-instrumented LLM calls,       │
│  arbitrary external agents without shared provenance root   │
└─────────────────────────────────────────────────────────────┘
```

**Trust rules**
- Content from tools is **not** trusted merely because the tool *integration* is trusted (e.g., Gmail server trusted → email body untrusted).
- Agents cannot authorize themselves for high-risk actions.
- Provenance metadata from an agent is accepted only if verifiable against the shared provenance service (or signed under the local trust root).
- Policy files and trust registry are admin-controlled, not agent-writable.

---

## 3. Attacker capabilities

### In scope

1. **Indirect prompt injection:** Craft content returned by `email.read`, `http.get`, filesystem reads, etc., containing instructions or values intended to influence later tool calls.
2. **Semantic evasion:** Paraphrase, summarize, synonymize, split across messages, encode/normalize destinations (Unicode, URL tricks), bury instructions in benign text.
3. **Cross-agent laundering:** Influence Agent A so that Agent B executes the sensitive sink without B reading the original source.
4. **Memory persistence:** Store transformed instructions in agent memory and retrieve later.
5. **Argument crafting:** Supply attacker-chosen recipients, URLs, paths, commands in tool arguments.
6. **Provenance forgery attempts:** Inject fake `parent_ids`, strip taint, replay old confirmations, present pruned lineage.
7. **Missing instrumentation abuse:** Route through uninstrumented LLM calls so explicit lineage is lost, hoping reconstruction fails.
8. **Confusion with benign similarity:** Produce text that looks like sensitive content to inflate false positives / force utility collapse (denial of service via overblocking is secondary but noted).

### Out of scope (MVP / stated limitations)

| Attack | Reason |
|--------|--------|
| Compromise of TCB (proxy, DB, policy store, confirmation UI) | Standard host security; assume TCB integrity |
| Model weight backdoors / training-time poisoning | Different threat class |
| Covert channels via timing / token counts | Research limitation (CaMeL notes similar) |
| Physical / social engineering of the human confirmer | Human is the recovery path |
| Fully malicious cooperating agent that controls the shared provenance DB | Shared root assumed honest |
| Prompt injection against a *policy-writing* LLM | Policies are code/config, not model-generated |
| Exploitation of vulnerabilities in Docker / host kernel | Ops responsibility; we sandbox but do not claim hypervisor security |
| Real-world zero-day in third-party MCP servers | Optional integrations; mock servers for core eval |

### Attacker limitations (assumptions)

- Cannot silently modify AgentTaint proxy code or policy store.
- Cannot forge HMAC/signatures without the local shared secret / key.
- Cannot obtain a CONFIRM token for action A and reuse it for action B (binding required).
- Cannot make the confirmation channel auto-approve without human action (MVP CLI).
- Does not control the user’s *initial* trusted instruction channel (USER origin).

---

## 4. Attack surfaces

1. Tool responses (primary).
2. Tool call arguments (sink).
3. Inter-agent message envelopes (content + claimed provenance).
4. Memory store contents.
5. Uninstrumented LLM I/O boundaries.
6. Confirmation / approval API.
7. Dashboard / audit APIs (read exposure + write if misconfigured).
8. Embedding / reconstruction subsystem (poisoning similarity corpus — lower priority).

---

## 5. Security objectives

| ID | Objective | Success criterion |
|----|-----------|-------------------|
| O1 | **Integrity of high-risk actions** | Untrusted content alone cannot cause ALLOW for HIGH-risk sinks without USER-specific authorization or CONFIRM |
| O2 | **Provenance observability** | For instrumented flows, full backward lineage is available for audit |
| O3 | **Honest uncertainty** | INFERRED never silently becomes KNOWN; UNKNOWN fails closed on designated HIGH-risk policies |
| O4 | **Utility preservation** | LOW-risk ops (summarize, list, read) remain available after reading untrusted content |
| O5 | **Explainability** | Every BLOCK/CONFIRM includes evidence channels, sources, and policy id |
| O6 | **Non-bypass at MCP boundary** | Sensitive tool calls cannot reach mock/real backends without proxy decision |

Non-goals for MVP: cryptographic proof-carrying IFC across mutually distrusting organizations; perfect causal attribution inside the LLM; zero false positives.

---

## 6. Policy-level security properties (target)

Informal properties (to be refined into Cedar / adapter rules):

1. **No untrusted externalization:** If an authority argument (recipient, URL, path sink) has only UNTRUSTED_TOOL / UNKNOWN lineage (KNOWN or high-confidence INFERRED), HIGH-risk send/post/exec is BLOCK or CONFIRM.
2. **User request grounding (CapLite-compatible mode):** Optional strict mode: authority args must appear in USER spans.
3. **Confirmation binding:** Approval applies to `(tool, canonical_args_hash, agent_id, expiry)` only.
4. **Fail closed:** If provenance service unavailable and tool risk ≥ HIGH and policy requires verification → BLOCK.
5. **Label non-authority:** Model-generated natural-language “explanations” never override policy decisions.

---

## 7. Residual risks (accepted)

- Reconstruction miss → false negative (attacker paraphrases beyond detection).
- Reconstruction over-match → false positive (utility loss).
- Incomplete SDK adoption → UNKNOWN provenance → overblocking or (if misconfigured) underblocking.
- CapLite-strict mode safe but low utility; AgentTaint-default mode higher utility, weaker absolute guarantee.
- Offline NeuroTaint-style causal LLM auditors are *not* in the TCB for MVP decisions (optional research module only).

---

## 8. Mapping to STRIDE (condensed)

| STRIDE | Example | Mitigation |
|--------|---------|------------|
| Spoofing | Fake provenance envelope | Shared service verification / HMAC |
| Tampering | Hash mismatch on span content | Content hash checks; reject |
| Repudiation | Denied tool call history | Append-only audit records |
| Information disclosure | Secrets in logs/dashboard | Redaction; hash-by-default |
| Denial of service | Flood proxy / force CONFIRM | Rate limits (post-MVP); fail closed |
| Elevation of privilege | Agent self-approval | Human confirmation; no agent policy write |

---

## 9. M9 review notes (implementation-backed)

- **Guarantees that require AgentTaint SDK instrumentation:** authenticated envelopes, parent-span maps on tool args, durable lineage across transforms/agents. Without instrumentation, expect PARTIAL/UNKNOWN and fail-closed/CONFIRM on HIGH-risk sinks.  
- **Estimates only:** reconstruction (INFERRED) similarity/support — never semantic causation.  
- **Residual threats confirmed in review:** MCP wire missing confirmation/candidate hooks; process-local nonce stores; optional dashboard local-trust auth. See `docs/m9_independent_review.md`.
