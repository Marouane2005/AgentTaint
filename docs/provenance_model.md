# Provenance Model

**Status:** Implemented through Milestone 3  
**Schema version:** 1

---

## Epistemic statuses (non-negotiable)

| Status | Definition | May authorize HIGH-risk alone? |
|--------|------------|--------------------------------|
| `KNOWN` | Explicit instrumentation or verified labeled I/O | Only if policy + trust rules say so |
| `INFERRED` | Reconstruction evidence only | Never treated as proof of causation; may raise scrutiny |
| `UNKNOWN` | No reliable origin | Fail closed for designated HIGH-risk |
| `PARTIAL` | Mix of known parents + gaps / incomplete instrumentation | Treated as insufficient where policy requires completeness |

**Promotion rule:** INFERRED → KNOWN only via a new explicit instrumentation event, never by threshold.

**Gap rule:** `SpanKind.GAP` spans are never `KNOWN`. Downstream SDK transforms that consume a gap become `PARTIAL`.

---

## Origins

- `USER` — direct user instructions / explicit authorizations  
- `TRUSTED_TOOL` — tool output classified as trusted *content* (rare; config-driven)  
- `UNTRUSTED_TOOL` — external content via tools  
- `INTERNAL` — system-generated with known lineage  
- `UNKNOWN` — insufficient provenance  

Integration trust ≠ content trust. Least-trust wins when merging parents.

---

## Transformation graph (Milestone 3)

### Explicit instrumentation

`ProvenanceRegistry.record_transformation(...)` creates:

1. An output span with `parent_ids`
2. Explicit edges (`SUMMARIZED_FROM`, `REWRITTEN_FROM`, …)
3. A `TransformationRecord` (`instrumentation=SDK` → may be `KNOWN` if parents are complete)

### Gap markers

`record_gap(reason, output_content, claimed_parent_ids=...)` for uninstrumented LLM calls or lost lineage:

- Creates `SpanKind.GAP`
- Status `PARTIAL` if some claimed parents exist and verify; else `UNKNOWN`
- Links present parents with `GAP_FROM`
- Records missing claims in metadata without inventing nodes

### Cross-agent transfer

`transfer_to_agent(sender, recipient, content, parent_span_ids)`:

- With verified parents → `AGENT_MESSAGE` + `TRANSFERRED_TO_AGENT` edges
- Without / missing parents → gap (does not invent lineage)

### Memory

`store_in_memory` / `retrieve_from_memory` preserve parent lineage through `STORED_IN_MEMORY` / `RETRIEVED_FROM_MEMORY`.

### Reconstruction (Milestone 4)

`agenttaint_reconstruction.ReconstructionEngine` scores argument values against a candidate text corpus (lexical / structural / optional semantic) and may call `attach_inferred_link(...)`.

- Attached spans are always **`INFERRED`**
- `confidence` remains **`null`** (uncalibrated)
- Support levels are ordinal hints, not P(causation)
- See `docs/reconstruction.md`

---

## Analysis APIs

| API | Purpose |
|-----|---------|
| `lineage_completeness(span_id)` | `LineageCompleteness` report (gaps, inferred edges, agents, untrusted sources) |
| `origin_conflicts(span_id)` | USER vs UNTRUSTED/UNKNOWN in explicit cone |
| `transformation_chain(span_id)` | Deterministic explicit chain from roots to span |
| `validate()` | Cycles, parent/edge mismatches, illegal GAP+KNOWN |

`is_complete=True` only when effective status is `KNOWN`, no gaps/partial/unknown/inferred ancestors, and no inferred edges.

---

## Core records

- `ProvenanceSpan`, `ProvenanceEdge`, `TransformationRecord`
- `LineageCompleteness`, `OriginConflict`
- `ToolCallDecision`, `ArgumentEvidence` (enforcement / future reconstruction)

### ArgumentEvidence rules

- Store `value_hash`, not raw secrets by default.
- Separate scores; `evidence_type`: `EXPLICIT` | `INFERRED`.
- `confidence` nullable until calibrated models exist.
