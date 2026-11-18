# Limitations

**Status:** Living document — update when behavior changes.

## Fundamental

1. **No perfect causal attribution inside LLMs.** Reconstruction estimates influence; it does not prove it.  
2. **Instrumentation dependency.** Uninstrumented transforms yield PARTIAL/UNKNOWN lineage.  
3. **Cooperating agents only.** Arbitrary third-party agents do not preserve provenance.  
4. **TCB assumption.** Compromised proxy/DB/policy store voids guarantees.  
5. **Adaptive paraphrase.** Semantic/lexical channels can fail; structural helps for explicit values only.  
6. **Utility vs security.** Fail-closed UNKNOWN increases false positives.  
7. **Benchmark external validity.** Custom scenarios may not match production agent frameworks.  
8. **Not CapLite-strong by default.** Request-grounding mode is optional; default mode trades absolute write integrity for utility.  
9. **Overlap with FIDES/NeuroTaint.** Novelty is not assumed.  
10. **Cedar:** Not enforced until the Cedar backend is implemented and tested.  
11. **Gap markers are honest, not magical:** an uninstrumented LLM call yields PARTIAL/UNKNOWN lineage; AgentTaint does not reconstruct missing transforms in Milestone 3.  
12. **Cross-agent transfer** only preserves lineage among AgentTaint-aware callers using authenticated envelopes / `transfer_to_agent` with verified parent ids.  
13. **Reconstruction is not causation:** lexical/structural/semantic support levels are not calibrated probabilities; attached edges are always INFERRED.  
14. **Adaptive evasion:** splitting identifiers across messages, novel encodings, and heavy paraphrase can yield UNKNOWN / false negatives.  
15. **Ambiguous structural values** (same email in USER and UNTRUSTED text) can produce multiple INFERRED matches — policy must still require explicit authorization.  
16. **Semantic embeddings** are optional; default CI uses a fixture embedder or disables the channel.  
17. **Envelope HMAC** (M5–M9) used a shared secret; M11 moved to per-agent keys (item 34). It is still symmetric HMAC, not mutual TLS or asymmetric identity.  
18. **Confirmation binding** protects the exact approved argument bytes; it does not prove the human understood semantic risk.  
19. **Cedar** remains deferred; production policy authors should not assume Cedar semantics yet.  
20. **Custom benchmark ceiling:** held-out scenarios are synthetic and often expose contiguous structural identifiers; near-zero ASR there does not transfer to production agents.  
21. **Semantic ablation** in CI/benchmark uses a fixture embedder, not a calibrated production model.  
22. **AgentDojo / InjecAgent** were not run in Milestone 6 — do not cite custom numbers as those benchmarks.  
23. **No comparative claim** vs CaMeL/FIDES/CapLite/NeuroTaint without a fair shared protocol.  
24. **M7 hard adaptive splits** can still evade fixture reconstruction (CONFIRM / provenance FN); BGE helps on this corpus but costs latency/memory.  
25. **Bootstrap multi-seed** quantifies sampling uncertainty on a fixed synthetic set — not stochastic LLM variance.  
26. **AgentDojo** is installable but full free/local ASR evaluation was not completed (LLM-backed protocol).  
27. **MCP wire:** confirmation IDs, parent span maps, and candidates travel in `_agenttaint` metadata on the protocol proxy; FastMCP helpers accept an `agenttaint` argument mapped to that object. Resources/prompts/SSE remain unsupported. Since M15 the agent cannot approve confirmations over MCP, cannot assert its own `agent_id`, and cannot override the provenance-context hash.  
28. **Durable nonce/confirmation stores** default to in-memory SQLite unless `AGENTTAINT_SECURITY_DB_URL` is set; a file or Postgres URL is required for out-of-band approval from another process. Postgres persistence (provenance graph, nonces, confirmations, concurrent single-use consume) runs in the CI `postgres` job against a `postgres:16` service container; the default job still uses SQLite. Atomic consume closes the check-then-set race for single-use approvals.  
29. **Registry availability** is probed with a live `SELECT 1` (manual override remains for tests only).  
30. **External benchmarks:** AgentDojo / InjecAgent full ASR remain **not evaluated** (see `docs/external_benchmarks_feasibility.md`).  
31. **MCP compatibility** is stdio multi-process client↔proxy↔backend for mock email/filesystem/http/shell — not full-spec conformance (`docs/mcp_compatibility_m10.md`).  
32. **Cancellation** is cooperative pre-forward only; an in-flight backend `tools/call` may still complete.  
33. **USER authorization** requires structured `(tool, argument, value)` grants scoped by agent/session — free-text USER spans are not scraped into allow-lists.  
34. **Envelope HMAC** uses **per-agent keys** via `AgentKeyring` for cooperating agents; unknown agents fail closed.  
35. **Control plane auth** defaults to local-trust; set `AGENTTAINT_API_AUTH=required` with `AGENTTAINT_DASHBOARD_TOKEN` on shared hosts.  
36. **Cedar** remains deferred (`docs/cedar_deferred.md`).  
37. **M13 zero ASR** on the synthetic suite is not general attack prevention.  
38. **External ASR** (AgentDojo / InjecAgent) remains not evaluated without an LLM.  
39. **Demo Compose** is a local research demo, not a hardened production deployment.
40. **Approval channel (M15):** approvals come only from the CLI or the token-gated control-plane endpoints. Anyone with the security database and `AGENTTAINT_CONFIRM_SECRET`, or the dashboard token, can approve; protect them like credentials. Approval does not prove the human understood the risk.
41. **Agent identity (M15)** is the proxy's configured `--agent-id`. Running several agents through one proxy process makes them indistinguishable; run one proxy per agent identity. `session_id` is still caller-supplied and only narrows grants.
42. **Declared lineage is agent-asserted.** An agent can still declare *wrong* parents (for example a USER span). Missing lineage is now treated as UNKNOWN and, for MEDIUM sinks, triggers CONFIRM once the session has ingested untrusted content; declaring a misleading parent is a residual risk that only reconstruction evidence can partially catch.
43. **Undeclared-lineage scrutiny is coarse for MEDIUM sinks:** after any untrusted read, every MEDIUM call without declared parents asks for confirmation (or blocks under `fail_closed_unknown_medium`). Agents that declare lineage keep full utility. The proxy only sees content that flows through it; untrusted input reaching the agent through other channels is invisible to this check.
44. **The synthetic suite does not exercise MEDIUM sinks** (only `email.read`/`email.send`), so the M15 MEDIUM-tier change has no measured effect on the published benchmark numbers; its utility impact is covered only by unit tests.
45. **Shell sandbox limits** are executed in the CI `docker-sandbox` job: commands run in a real container and the tests check uid/gid 65534, empty capability sets, no-new-privileges, loopback-only networking, read-only rootfs, noexec `/tmp`, cgroup memory/CPU/pids limits and the kill timeout. Docker is not a VM boundary; kernel escapes are out of scope.
46. **Reconstruction's added value** over explicit lineage is not demonstrated on the current suite (`explicit_only` and `combined` have identical decision metrics).

## Operational

- Embedding model download requires network once.  
- Shell demo requires Docker; otherwise disabled.  
- `AGENTTAINT_CONFIRM_SECRET` has no default: the proxy refuses to start without a random secret of at least 32 characters (`make demo` generates one per run).  
- Dashboard without backend shows empty states — never fabricated metrics.  
- **M8 demo seed** is a labeled SIMULATED scenario through the real SecurityGateway — not production telemetry.  
- Dashboard sessions are in-memory by default; restart clears live audit/provenance (benchmark `reports/` on disk persist).  
- The UI is read-mostly and does not offer operator overrides that weaken the gateway.  
- Control plane is **local-trust** (loopback by default). Optional `AGENTTAINT_DASHBOARD_TOKEN` gates mutations; do not expose `HOST=0.0.0.0` without a token on untrusted networks.  
- See [docs/security_review_m8.md](security_review_m8.md) and [docs/m9_independent_review.md](m9_independent_review.md).
