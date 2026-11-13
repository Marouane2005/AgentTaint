# Research Log

Append-only notes. Failures welcome.

## 2026-11-13 — Feasibility assessment kickoff

**Decision:** Complete Tasks A–G documentation before coding.

**Literature takeaway:** CaMeL/FIDES/CapLite already provide strong *online* defenses; NeuroTaint already targets *semantic* offline taint. AgentTaint’s honest research niche is MCP-boundary online enforcement + multi-agent authenticated lineage + explicit KNOWN/INFERRED epistemology with ablation—not “first provenance system.”

**Architecture decision:** PolicyAdapter interface first; Cedar via `cedarpy` later. SQLite + NetworkX for MVP graph persistence/traversal.

**Hypothesis:** Explicit + structural/lexical (and optional semantic) evidence at proxy can block cross-agent transformed exfiltration while allowing low-risk reads.

**Risk:** Overlap with NeuroTaint may make “novelty” hard to claim; optimize for reproducible platform + honest eval.
