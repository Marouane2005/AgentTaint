# MVP Definition — AgentTaint

**Status:** Research assessment  
**Date:** 2026-11-13

---

## Research hypothesis (MVP-scoped)

> In a multi-agent MCP setting, **explicit provenance instrumentation** plus **structural/lexical reconstruction** at a security proxy can block high-risk tool calls whose authority arguments descend from untrusted tool content—even after summarization and delegation—while still allowing low-risk reads/summaries.

Semantic embeddings are **in-scope for the full system** but **optional for the first vertical slice** (feature-flagged) so CI stays free and fast.

---

## Smallest system that tests the hypothesis

One vertical slice:

1. Provenance registry (SQLite) + source labeler  
2. MCP proxy in front of mock `email.*` (+ optionally filesystem)  
3. SDK: `summarize` + `delegate` + `accept`  
4. Reconstruction: structural (email/URL) + lexical; explicit lineage walk  
5. Deterministic policy: ALLOW low-risk / BLOCK untrusted recipient on `email.send` / CONFIRM on UNKNOWN high-risk  
6. CLI confirmation stub  
7. Custom scenario suite (≥10 malicious, ≥10 benign) with recorded metrics  
8. Pytest unit + integration + security (forgery, hash mismatch)  
9. Minimal FastAPI audit endpoints (enough for later dashboard)

**Out of MVP:** Next.js polish, Cedar, AgentDojo/InjecAgent full integration, real MCP SaaS, Ollama, shell Docker (can stub), paper results section.

---

## Demo script (must work)

```
1. Load mock inbox containing attacker@example.com + exfil instruction
2. Agent A: email.read → UNTRUSTED span
3. Agent A: SDK summarize → child span SUMMARIZED_FROM
4. Agent A: SDK delegate → Agent B envelope (verified)
5. Agent B: email.send(to=attacker@example.com, ...)
6. Proxy: BLOCK (or CONFIRM) with provenance chain S_send ← S_summary ← S_email
7. Agent B: email.read or summarize-only → ALLOW
8. User-authorized recipient present in USER span → ALLOW send
```

---

## Acceptance criteria (MVP done when)

| # | Criterion |
|---|-----------|
| M1 | All MVP tests green on CPU without API keys |
| M2 | Demo script reproducible via `make demo` / script |
| M3 | Decision records show KNOWN vs INFERRED correctly |
| M4 | Forged provenance envelope rejected |
| M5 | No plaintext attacker payload required in audit defaults (hash + redaction) |
| M6 | Docs: threat model + architecture + limitations match actual behavior |
| M7 | No dashboard fake metrics |

---

## Success metrics for custom benchmark (honest)

Report only measured values:

- ASR on transformed + cross-agent malicious scenarios  
- Legitimate task success on benign scenarios  
- FP rate on benign sends that are user-authorized  
- Median / p95 enforcement latency  

No invented baselines.
