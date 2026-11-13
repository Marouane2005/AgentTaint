# Technical Feasibility — AgentTaint

**Status:** Research assessment (pre-implementation)  
**Date:** 2026-11-13

---

## Task C verdict

**Cross-agent provenance propagation is feasible for cooperating, instrumented agents** that share an AgentTaint provenance service and use the SDK for transformations and delegation.

**It is not feasible to guarantee** token-level information-flow tracking across arbitrary uninstrumented LLM generations, or across third-party agents that do not participate in the trust root.

AgentTaint must therefore ship as a **hybrid**:

| Layer | What it provides | Epistemic status |
|-------|------------------|------------------|
| SDK instrumentation | Explicit parent links for summarize / rewrite / memory / delegate | **KNOWN** |
| MCP proxy labeling | Origin labels on tool results; argument inspection at sinks | **KNOWN** for labeled I/O |
| Reconstruction | Lexical / semantic / structural evidence linking args ↔ prior untrusted spans | **INFERRED** |
| Missing instrumentation | Detected gaps | **UNKNOWN** / PARTIAL |

---

## What can be guaranteed (engineering guarantees)

These are *system* guarantees under the threat-model assumptions (TCB intact, agents use proxy + SDK as specified):

1. **No silent bypass of the MCP proxy** for configured backends: tool calls are only forwarded after a recorded decision.
2. **Explicit lineage persistence** for SDK-wrapped transforms: output spans retain `parent_ids` and transformation records.
3. **Cross-agent envelope verification** for cooperating agents: receiver rejects messages whose provenance refs are missing, hash-mismatched, or not present in the shared registry.
4. **Fail-closed HIGH-risk** when policy requires verified provenance and the registry is unavailable.
5. **Confirmation binding** to canonical argument hashes (no generic “approve all”).
6. **Audit completeness** for intercepted calls: every decision yields a `ToolCallDecision` record.
7. **KNOWN ≠ INFERRED** in the data model: schema and APIs forbid upgrading evidence type without a new explicit instrumentation event.

---

## What can only be estimated

1. Whether untrusted content *caused* a tool argument after paraphrasing (reconstruction scores).
2. Completeness of lineage when any LLM call skips the SDK.
3. Semantic similarity thresholds that generalize across domains and adaptive attackers.
4. Transfer performance of embedding model `BAAI/bge-small-en-v1.5` on security-critical short strings (emails, URLs).
5. End-to-end ASR reduction on AgentDojo / InjecAgent relative to CapLite / FIDES / NeuroTaint—**unknown until measured**.

---

## MCP proxy feasibility

**Feasible.** The official MCP Python ecosystem supports:

- Client connections to backend servers (stdio / SSE / HTTP).
- Proxy / mount patterns (e.g., FastMCP `from_client` / server composition).
- Middleware hooks around `tools/call` for inspect → allow/deny.

**MVP approach (recommended):**

1. Implement AgentTaint proxy as an MCP server that aggregates mock tool servers.
2. On `tools/call`: classify risk → reconstruct evidence → evaluate policy → ALLOW forward / BLOCK error / CONFIRM wait.
3. On tool results: create provenance spans with origin labeling before returning to the agent.

**Supported initially:** tool list, tool call, result labeling, errors, audit log.  
**Deferred:** resources/prompts full fidelity, sampling, complex OAuth MCP auth, multi-tenant SaaS.

**Risk:** MCP SDK middleware APIs are evolving (“provisional” in places). Mitigate by wrapping a thin internal interface so SDK upgrades do not rewrite policy logic.

---

## Cross-agent propagation feasibility

**Reliable when:**

- Both agents use AgentTaint SDK.
- Both talk to the same provenance service (SQLite/Postgres) over localhost or authenticated channel.
- Delegation uses structured envelopes; content hashes match registry.

**Unreliable when:**

- Agents communicate via free-text chat without envelopes.
- A non-AgentTaint agent is in the path.
- Serialization drops provenance fields (must validate schema on receive).

**MVP guarantee language:** “Provenance-preserving among AgentTaint-aware agents sharing a provenance root,” not “arbitrary multi-agent systems.”

---

## Cedar feasibility

**Feasible via `cedarpy` (Apache-2.0 / open Cedar engine bindings)** — no paid API.

**Milestone plan:** Week 1–4 use a **deterministic PolicyAdapter** interface with YAML/JSON rules + tests. Week 5 add Cedar backend implementing the same interface. Do not claim Cedar enforcement until the Cedar backend is wired and tested.

---

## Reconstruction feasibility

| Channel | Feasibility | Notes |
|---------|-------------|-------|
| Lexical | High | Exact / n-gram / token Jaccard; cheap; brittle to paraphrase |
| Structural | High | Regex extract emails, URLs, IPs, paths; normalize; strong for authority args |
| Semantic | Medium | `sentence-transformers` + `bge-small-en-v1.5` on CPU; ~33M params; disk ~100MB+; cosine ≠ causation |
| Aggregation | Medium | Transparent weighted score + thresholds; calibration later with labeled data |

**CPU:** Acceptable for MVP-scale graphs (hundreds–thousands of spans). Benchmark p95 latency as a release gate.

**Do not** use a paid embedding API.

---

## Benchmark feasibility

| Benchmark | Feasibility | Plan |
|-----------|-------------|------|
| Custom cross-agent | High | First-class; fully controlled; required for hypothesis |
| AgentDojo | Medium–High | Integrate as optional extra; adapter layer; document gaps |
| InjecAgent | Medium | Often single-turn; good transfer test; not provenance-labeled |
| Head-to-head vs CaMeL/FIDES/NeuroTaint | Medium–Low | Reuse public code where licenses allow; otherwise reimplement *baselines* and label them as such |

---

## Major technical risks

1. **Overclaiming causation** from cosine similarity → mitigated by epistemology + ablation.
2. **Utility collapse** from fail-closed UNKNOWN → need risk tiers + CONFIRM.
3. **SDK adoption gap** → proxy still labels tool I/O; document incomplete coverage.
4. **MCP SDK churn** → internal ports/adapters.
5. **Embedding cold start** (download) → pin model; vendor in Docker image optional; document offline after first pull.
6. **NeuroTaint overlap** → position as online MCP + multi-agent + policy research platform; measure, don’t market.

---

## Go / no-go

**GO for MVP** focused on:

instrumented provenance + MCP proxy enforcement + structural/lexical reconstruction + deterministic policy + custom cross-agent benchmark.

**CONDITIONAL** for semantic embeddings (include behind feature flag; tests must pass with embeddings mocked).

**DEFER** full AgentDojo/InjecAgent parity and Cedar until after core path works.
