# Architecture — AgentTaint

**Status:** Living — implementation through M8; M9 audit notes appended  
**Date:** 2026-11-13

---

## 1. Component diagram

```
                    ┌──────────────────────────────┐
                    │  Agent A / Agent B (+ SDK)   │
                    │  transform / memory / delegate│
                    └──────────────┬───────────────┘
                                   │ MCP (stdio/SSE)
                                   ▼
                    ┌──────────────────────────────┐
                    │     AgentTaint MCP Proxy     │
                    │  discover · intercept · audit│
                    └──────┬───────────┬───────────┘
           label results   │           │  enforce calls
                           ▼           ▼
              ┌────────────────┐  ┌────────────────┐
              │ Source Labeler │  │  Risk Engine   │
              │ Trust Registry │  │ Tool Classifier│
              └───────┬────────┘  └────────┬───────┘
                      │                    │
                      ▼                    ▼
              ┌────────────────┐  ┌────────────────┐
              │ Provenance     │  │ Reconstruction │
              │ Graph Engine   │◄─┤ Evidence Agg.  │
              └───────┬────────┘  └────────┬───────┘
                      │                    │
                      └──────────┬─────────┘
                                 ▼
                      ┌────────────────────┐
                      │   Policy Engine    │
                      │ ALLOW│BLOCK│CONFIRM│
                      └─────────┬──────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        Mock Email         Mock FS/HTTP      Mock Shell
        MCP Server         MCP Servers       (Docker)
              │
              ▼
        Audit Store ←── Dashboard API (FastAPI) ←── Next.js UI
```

**Independence rule:** Policy and provenance packages must be importable and testable without the dashboard or any LLM.

---

## 2. Data-flow (attack scenario)

```
[email.read] ──UNTRUSTED_TOOL span S0──► Agent A
     │
     │ SDK summarize
     ▼
  span S1 (SUMMARIZED_FROM S0) ──store──► Memory M1
     │
     │ SDK delegate envelope
     ▼
  Agent B receives msg (refs S1, verified)
     │
     │ proposes email.send(to=attacker@…, file=customers.csv)
     ▼
  Proxy: risk=HIGH
     │
     ├─ explicit lineage? (args ← S1 ← S0) 
     ├─ structural: email in S0
     ├─ lexical/semantic: optional
     ▼
  Policy: untrusted authority arg → BLOCK or CONFIRM
     │
     ▼
  ToolCallDecision + explanation chain
```

---

## 3. Provenance graph design

### Node kinds (`ProvenanceSpan.kind`)

`SOURCE`, `EXTRACT`, `SUMMARY`, `REWRITE`, `MEMORY`, `AGENT_MESSAGE`, `TOOL_ARG`, `TOOL_RESULT`, `USER_INSTRUCTION`

### Edge kinds

`EXTRACTED_FROM`, `SUMMARIZED_FROM`, `REWRITTEN_FROM`, `STORED_IN_MEMORY`, `RETRIEVED_FROM_MEMORY`, `TRANSFERRED_TO_AGENT`, `DERIVED_FROM`, `USED_IN_TOOL_ARGUMENT`

### Provenance status

| Status | Meaning |
|--------|---------|
| `KNOWN` | Created by instrumentation or verified tool I/O labeling |
| `INFERRED` | Linked only by reconstruction evidence |
| `UNKNOWN` | No reliable origin |
| `PARTIAL` | Some parents known; gaps recorded |

### Uncertainty propagation

- Edge from KNOWN→KNOWN via SDK = KNOWN.
- Any reconstruction-only edge = INFERRED (never auto-promote).
- Missing parent at a transform boundary = PARTIAL + `gap` marker node.

### In-memory vs persistent

- **NetworkX** (or adjacency lists) for traversal in a request.
- **SQLAlchemy** tables for durable spans/edges (SQLite → Postgres).
- Graph DB migration later: keep repository interface `ProvenanceStore`.

---

## 4. Database schema (MVP)

```sql
-- provenance_spans
span_id            TEXT PRIMARY KEY,
origin             TEXT NOT NULL,  -- USER|TRUSTED_TOOL|UNTRUSTED_TOOL|INTERNAL|UNKNOWN
kind               TEXT NOT NULL,
source_tool        TEXT,
agent_id           TEXT,
content_hash       TEXT NOT NULL,  -- sha256
content_redacted   TEXT,           -- optional, retention-controlled
embedding_id       TEXT,
provenance_status  TEXT NOT NULL,  -- KNOWN|INFERRED|UNKNOWN|PARTIAL
confidence         REAL,           -- null for KNOWN explicit
created_at         TEXT NOT NULL,
schema_version     INTEGER NOT NULL DEFAULT 1

-- provenance_edges
edge_id            TEXT PRIMARY KEY,
src_span_id        TEXT NOT NULL REFERENCES provenance_spans,
dst_span_id        TEXT NOT NULL REFERENCES provenance_spans,
relationship       TEXT NOT NULL,
evidence_type      TEXT NOT NULL,  -- EXPLICIT|INFERRED
metadata_json      TEXT,
created_at         TEXT NOT NULL

-- transformations
transformation_id  TEXT PRIMARY KEY,
operation          TEXT NOT NULL,
output_span_id     TEXT NOT NULL,
agent_id           TEXT,
model              TEXT,
instrumentation    TEXT NOT NULL,  -- SDK|RECONSTRUCTION|NONE
created_at         TEXT NOT NULL

-- transformation_inputs (M2M)
transformation_id  TEXT,
input_span_id      TEXT,
PRIMARY KEY (transformation_id, input_span_id)

-- tool_call_decisions
call_id            TEXT PRIMARY KEY,
agent_id           TEXT,
tool_name          TEXT NOT NULL,
risk_tier          TEXT NOT NULL,
arguments_hash     TEXT NOT NULL,
arguments_redacted_json TEXT,
provenance_status  TEXT,
decision           TEXT NOT NULL,  -- ALLOW|BLOCK|CONFIRM
policy_id          TEXT,
evidence_json      TEXT,
latency_ms         INTEGER,
created_at         TEXT NOT NULL

-- confirmations
confirmation_id    TEXT PRIMARY KEY,
call_id            TEXT NOT NULL,
args_hash          TEXT NOT NULL,
status             TEXT NOT NULL,  -- PENDING|APPROVED|DENIED|EXPIRED
expires_at         TEXT,
resolved_at        TEXT

-- trust_registry
entry_id           TEXT PRIMARY KEY,
tool_name          TEXT NOT NULL,
content_policy     TEXT NOT NULL,  -- e.g. RESULTS_UNTRUSTED
risk_override      TEXT,
notes              TEXT
```

Indexes: `content_hash`, `agent_id`, `created_at`, `tool_name`, edge endpoints.

---

## 5. API specification (FastAPI — control plane)

Base: `http://127.0.0.1:8080/api/v1`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/spans` | Create span (SDK / proxy) |
| GET | `/spans/{id}` | Fetch span metadata |
| GET | `/spans/{id}/ancestors` | Backward provenance |
| GET | `/spans/{id}/descendants` | Forward lineage |
| POST | `/transformations` | Record SDK transform |
| POST | `/agents/delegate` | Validate + accept envelope |
| POST | `/enforce/preview` | Evaluate tool call without executing |
| GET | `/decisions` | List audit decisions |
| GET | `/decisions/{id}` | Decision + evidence |
| POST | `/confirmations/{id}/resolve` | Human approve/deny |
| GET | `/metrics/overview` | Dashboard counters |
| GET | `/graph/export` | Nodes/edges for UI |
| GET | `/health` | Liveness + DB |

Auth (MVP): shared local bearer token / HMAC between SDK, proxy, API. No public internet assumption.

---

## 6. MCP integration design

### Proxy responsibilities

1. `tools/list` — union of backend tools with risk metadata annotations (internal).
2. `tools/call` — **mandatory** enforcement path; never forward HIGH-risk without decision.
3. Label each tool result as a span before returning.
4. Map MCP errors for BLOCK (`PermissionError`-style message + decision id).
5. CONFIRM — return structured error/result instructing agent to wait; CLI approves; agent retries with confirmation id **or** proxy holds and resumes (MVP: deny-until-approved + retry).

### Mock servers (integrations/)

| Server | Tools | Sandbox |
|--------|-------|---------|
| mock_email | `email.read`, `email.send` | Fixture inbox JSON |
| mock_filesystem | `filesystem.read`, `filesystem.write` | Temp workspace dir |
| mock_http | `http.get`, `http.post` | Local aiohttp test server |
| mock_shell | `shell.execute` | Docker container, no host shell |

### Trust registry examples

```yaml
tools:
  email.read:
    integration_trust: TRUSTED_TOOL_SERVER
    result_origin: UNTRUSTED_TOOL
  email.send:
    default_risk: HIGH
  filesystem.read:
    result_origin: UNTRUSTED_TOOL  # unless path allowlisted as INTERNAL
  shell.execute:
    default_risk: HIGH
```

---

## 7. Agent SDK surface (minimal)

```python
# Conceptual API — exact names may refine during implementation
class AgentTaintContext:
    async def summarize(self, text, parent_span_ids, model=None) -> ProvenanceSpan
    async def rewrite(self, text, parent_span_ids) -> ProvenanceSpan
    async def remember(self, span_id, key) -> ProvenanceSpan
    async def recall(self, key) -> ProvenanceSpan
    async def delegate(self, recipient_agent, content, parent_span_ids) -> Envelope
    async def accept(self, envelope) -> ProvenanceSpan  # verifies refs
```

Uninstrumented LLM calls: SDK helper `mark_untracked(output)` → UNKNOWN/PARTIAL gap.

---

## 8. Security policy examples

### Deterministic adapter (MVP)

```yaml
policies:
  - id: allow-low-risk
    when: { risk_tier: LOW }
    decision: ALLOW

  - id: block-untrusted-external-recipient
    when:
      risk_tier: HIGH
      tool: email.send
      any_argument:
        name: to
        structural_match_untrusted: true
        not_user_authorized: true
    decision: BLOCK

  - id: confirm-unknown-high-risk
    when:
      risk_tier: HIGH
      provenance_status: [UNKNOWN, PARTIAL]
    decision: CONFIRM

  - id: allow-user-authorized-recipient
    when:
      tool: email.send
      argument_to_in_user_spans: true
    decision: ALLOW
```

### Cedar sketch (post-MVP backend)

```cedar
forbid (
  principal,
  action == Action::"email.send",
  resource
) when {
  context.risk_tier == "HIGH" &&
  context.args.to.untrusted_influence == true &&
  context.args.to.user_authorized == false
};

permit (
  principal,
  action == Action::"email.read",
  resource
);
```

---

## 9. Risk classification (initial)

| Tier | Tools (default) |
|------|-----------------|
| LOW | `email.read`, `filesystem.read`, `http.get` (allowlisted hosts), summarize-only paths |
| MEDIUM | `filesystem.write` (non-sensitive paths), draft creation |
| HIGH | `email.send`, `http.post`, `shell.execute`, sensitive path writes |

Overrides via config; classifier is deterministic (name + schema + arg features), not an LLM.

---

## 10. Frontend architecture

- Next.js app reads **only** from FastAPI control plane.
- No simulated decisions in the UI.
- Graph explorer: fetch `/graph/export` + `/decisions/{id}`.
- Benchmark lab: reads `benchmarks/reports/*.json` produced by real runs (empty state = no fabricated numbers).

---

## 11. Package layout (adjusted)

```
agenttaint/
  packages/
    core/            # types, hashing, config
    provenance/      # registry, graph, store
    reconstruction/  # lexical, structural, semantic, aggregate
    policy/          # PolicyAdapter + later Cedar
    risk/            # tool risk classifier
    mcp_proxy/       # enforcement boundary
    agent_sdk/       # instrumentation
    memory/          # provenance-aware memory
    audit/           # decision records
    api/             # FastAPI control plane
  integrations/      # mock MCP servers
  apps/dashboard/    # Next.js
  benchmarks/
  policies/
  tests/
  docs/
```

Empty packages will not be created ahead of need; modules appear when implemented.

---

## M9 architecture audit notes

- Default MCP gateway builder now loads **provenance-aware** policy (`policies/provenance_policy.yaml`); stub remains available via `*stub*` policy paths.  
- `SecurityGateway.invoke` is the single enforcement chokepoint: non-ALLOW never calls `backend.call_tool`.  
- FastMCP tool wrappers currently pass only tool-native arguments — **not** confirmation tokens / parent maps / reconstruction candidates. Those remain SDK/library parameters.  
- Dashboard `agenttaint-api` is a local control plane over the same stores; it must not bypass the gateway (demo seed still uses live `SecurityGateway`).  
- Full detail: `docs/m9_independent_review.md`, `docs/mcp_compatibility_m9.md`.
