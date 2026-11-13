# Milestone 9 — Independent Review Report

**Role:** Senior security / research reviewer (adversarial stance).  
**Scope:** Code as of branch `m9-research-readiness`.  
**Method:** Implementation inspection, adversarial regression, reproduction of saved reports, external-benchmark feasibility.  
**Non-goals:** Dashboard redesign; inventing features to look more impressive; overwriting M6/M7 result artifacts.

---

## Executive verdict

**B — Suitable for a public research/portfolio demo, but needs more engineering before a claim of production-grade MCP security.**

Evidence:

- Core library guarantees (BLOCK never invokes backend; INFERRED ≠ KNOWN; envelope HMAC/replay/expiry; confirmation binding) are **verified by tests**, including new M9 adversarial suite.
- Several **High/Medium** issues were confirmed and partially fixed in M9 (default MCP stub policy, audit `confirmation_id` drop, decision provenance rewrite, nested redaction, token compare).
- Residual blockers remain: MCP wire does not expose confirmation/parent spans/candidates; envelope/confirmation state is process-local; registry unavailability is a manual flag; no full AgentDojo/InjecAgent ASR under free/local constraints; MCP “compatibility” is in-process FastMCP, not multi-process protocol conformance.

Zero ASR on the synthetic custom suite is **not** general attack prevention.

---

## Prioritized findings

### Verified vulnerabilities / defects

| ID | Severity | Component / file | Finding | Impact | Fix (M9) | Regression |
|----|----------|------------------|---------|--------|----------|------------|
| F1 | **High** | `mcp_proxy/server.py` `build_gateway_from_paths` | Default policy was **StubPolicy** (`allow_by_default`), so HIGH-risk `email.send` without lineage could ALLOW | Advertised provenance-aware enforcement not active on default MCP path | Default now `provenance_policy.yaml`; stub only if path name contains `stub` | `test_m9_default_proxy_builder_uses_provenance_policy` |
| F2 | **Medium** | `audit/store.py` | `confirmation_id` dropped on persist | Audit trail incomplete for CONFIRM flows | Column + round-trip | `test_m9_audit_persists_confirmation_id` |
| F3 | **Medium** | `mcp_proxy/gateway.py` | After ALLOW, decision `provenance_status` UNKNOWN rewritten from **result** span KNOWN | Silent upgrade of authorization provenance in audit | Removed rewrite | `test_m9_decision_provenance_not_upgraded_from_result_span` |
| F4 | **Low** | `mcp_proxy/gateway.py` `_redact_arguments` | Only top-level strings redacted | Nested emails/URLs leaked into audit JSON | Recursive redaction | `test_m9_nested_argument_redaction` |
| F5 | **Low** | `api/app.py` | Dashboard token compared with `!=` | Timing side channel (local-trust context) | `hmac.compare_digest` | existing token tests |
| F6 | **Low** | `api/app.py` health | Hard-coded `registry_ok`/`audit_ok` | False sense of health | Probe list operations | covered by health tests |

### Concerns (not claimed as exploited bugs)

| ID | Severity | Concern | Notes |
|----|----------|---------|-------|
| C1 | High (residual) | MCP tool signatures lack `confirmation_id`, parent spans, reconstruction candidates | Library supports them; FastMCP wrappers do not — confirmation/reconstruction cannot be used end-to-end via default MCP tools |
| C2 | Medium | Envelope `NonceStore` / confirmation store are in-memory | Multi-process / restart replay windows |
| C3 | Medium | `registry_available` is a **manual boolean**, not outage detection | Exception paths during registry I/O may still surface as 500s rather than fail-closed policy |
| C4 | Medium | Dashboard GET routes remain unauthenticated | Acceptable for loopback demo; not for shared hosting |
| C5 | Medium | USER authorization is string equality on authority args | Homoglyphs tested as non-match; not full IDNA/punycode policy |
| C6 | Low | Graph integrity `validate()` is opt-in | Not run on every write |
| C7 | Low | Audit rows lack cryptographic integrity seals | Tamper-evident log not claimed |

---

## Guarantee validation (scenarios 1–14)

| # | Scenario | Result |
|---|----------|--------|
| 1 | Forged envelopes | **Pass** — signature rejected |
| 2 | Valid sig / missing parents | **Pass** — seal/verify rejects |
| 3 | Replay | **Pass** — nonce store |
| 4 | Expired metadata | **Pass** — max_age |
| 5 | Args changed after confirmation | **Pass** |
| 6 | Reused confirmation | **Pass** |
| 7 | Registry unavailable (HIGH) | **Pass** — BLOCK, no backend |
| 8 | Multi-summary untrusted | **Pass** — BLOCK, INFERRED evidence |
| 9 | Multi-agent transfer | **Pass** — lineage retained |
| 10 | Semantic similarity ≠ causation | **Pass** — INFERRED only, `confidence=None` |
| 11 | Conflicting USER+UNTRUSTED | **Pass** — USER exact auth path documented; not silent |
| 12 | Missing instrumentation | **Pass** — GAP ≠ KNOWN |
| 13 | Unicode / homoglyph | **Pass** — no USER-auth bypass |
| 14 | Gateway bypass / BLOCK | **Pass** — sink empty |

Suite: `tests/unit/test_m9_adversarial_guarantees.py`.

---

## Fixes shipped in M9 (correctness only)

1. Default MCP gateway → provenance-aware policy.  
2. Persist `confirmation_id` in audit store.  
3. Stop upgrading decision provenance from tool-result spans.  
4. Recursive argument redaction.  
5. Constant-time dashboard token compare; honest health probes.  
6. Adversarial regression tests + documentation package.

**Policy thresholds / benchmark configs were not retuned to improve ASR.**

---

## Remaining blockers before public release

1. Expose confirmation + parent-span + candidate hooks on MCP tool wire (or document “SDK-only”).  
2. Durable nonce/confirmation stores for multi-process.  
3. Automatic fail-closed on registry I/O failure.  
4. Independent AgentDojo/InjecAgent evaluation **or** permanent “not evaluated” labeling (already preferred).  
5. Multi-process MCP client↔proxy↔backend conformance tests.  
6. AuthN/Z model if the control plane is ever network-exposed.

---

## Related M9 docs

- [benchmark_validity_m9.md](benchmark_validity_m9.md)  
- [external_benchmarks_feasibility.md](external_benchmarks_feasibility.md)  
- [mcp_compatibility_m9.md](mcp_compatibility_m9.md)  
- Updated: `limitations.md`, `threat_model.md`, `architecture.md`, `provenance_model.md`, `security_policies.md`, `benchmark_methodology.md`, `related_work.md`, `mcp_proxy.md`
