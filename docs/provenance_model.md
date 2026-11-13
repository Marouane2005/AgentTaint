# Provenance Model

**Status:** Design (pre-implementation)  
**Schema version:** 1

---

## Epistemic statuses (non-negotiable)

| Status | Definition | May authorize HIGH-risk alone? |
|--------|------------|--------------------------------|
| `KNOWN` | Explicit instrumentation or verified labeled I/O | Only if policy + trust rules say so |
| `INFERRED` | Reconstruction evidence only | Never treated as proof of causation; may raise scrutiny |
| `UNKNOWN` | No reliable origin | Fail closed for designated HIGH-risk |
| `PARTIAL` | Mix of known parents + gaps | Treated as insufficient where policy requires completeness |

**Promotion rule:** INFERRED → KNOWN only via a new explicit instrumentation event, never by threshold.

---

## Origins

- `USER` — direct user instructions / explicit authorizations  
- `TRUSTED_TOOL` — tool output classified as trusted *content* (rare; config-driven)  
- `UNTRUSTED_TOOL` — external content via tools  
- `INTERNAL` — system-generated with known lineage  
- `UNKNOWN` — insufficient provenance  

Integration trust ≠ content trust.

---

## Core records

See `docs/architecture.md` for SQL and JSON field definitions for:

- `ProvenanceSpan`
- `TransformationRecord`
- `ToolCallDecision`
- `ArgumentEvidence`

### ArgumentEvidence rules

- Store `value_hash`, not raw secrets by default.
- Separate scores: `lexical_score`, `semantic_score`, `structural_match`, `explicit_lineage`.
- `evidence_type`: `EXPLICIT` | `INFERRED`.
- `confidence` nullable until calibrated models exist; do not invent probabilities.

---

## Graph queries

- **Backward:** from tool argument span → sources (enforcement).  
- **Forward:** from untrusted source → sinks (forensics).  
- **Uncertainty:** any path containing only INFERRED edges is an inferred path.
