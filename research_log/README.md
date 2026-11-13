# Research Log

Append-only notes. Failures welcome.

## 2026-11-13 — Feasibility assessment kickoff

**Decision:** Complete Tasks A–G documentation before coding.

**Literature takeaway:** CaMeL/FIDES/CapLite already provide strong *online* defenses; NeuroTaint already targets *semantic* offline taint. AgentTaint’s honest research niche is MCP-boundary online enforcement + multi-agent authenticated lineage + explicit KNOWN/INFERRED epistemology with ablation—not “first provenance system.”

**Architecture decision:** PolicyAdapter interface first; Cedar via `cedarpy` later. SQLite + NetworkX for MVP graph persistence/traversal.

**Hypothesis:** Explicit + structural/lexical (and optional semantic) evidence at proxy can block cross-agent transformed exfiltration while allowing low-risk reads.

**Risk:** Overlap with NeuroTaint may make “novelty” hard to claim; optimize for reproducible platform + honest eval.

## 2026-11-13 — Milestone 1 landed

**Implemented:** `agenttaint-core` schemas/hashing/config; `agenttaint-provenance` SQLite store, NetworkX graph, trust registry, source labeler, registry API; unit tests (15 passing).

**Decision:** Refuse INFERRED edges targeting KNOWN spans so reconstruction cannot silently “confirm” lineage.

**Next:** MCP proxy + mock email server (Milestone 2).

## 2026-11-13 — Milestone 2 landed

**Implemented:** mock email backend/MCP server; risk classifier; stub policy adapter + YAML; audit store; `SecurityGateway` enforcement path; FastMCP security proxy with in-memory MCP integration tests.

**Decision:** Keep enforcement MCP-transport-agnostic (`SecurityGateway`) and wrap with FastMCP for protocol compatibility. BLOCK raises `ToolError` and never calls the backend.

**Pinned:** `mcp>=1.23.0,<2` (1.12.x broke on current pydantic).

**Not claimed:** Cedar, multi-process remote MCP fan-out, resources/prompts proxying, dashboard.

**Next:** Milestone 3 transform graph completeness / gap markers (or fold residual graph work into reconstruction prep).

## 2026-11-13 — Milestone 3 landed

**Implemented:** multi-step transformation chains; `record_gap` (never KNOWN); `transfer_to_agent`; memory store/retrieve; `LineageCompleteness` + `OriginConflict`; `attach_inferred_link` hook; stricter graph validation (parent/edge mismatch, GAP≠KNOWN).

**Invariant preserved:** incomplete parents force PARTIAL on downstream SDK transforms; INFERRED cannot attach to KNOWN.

**Tests:** 45 passing (added transformation graph suite).

**Next:** Milestone 4 reconstruction (lexical/structural/semantic + ablation).

## 2026-11-13 — Milestone 4 landed

**Implemented:** `agenttaint-reconstruction` with lexical, structural (incl. common obfuscation), optional semantic (fixture backend in tests), transparent support aggregation, ablation modes, INFERRED-only attachment via `attach_inferred_link`.

**Decision:** Keep candidate plaintext in a side corpus (`CandidateRecord`) so audit/provenance DB can remain redacted-by-default.

**Honest failures:** split-recipient attacks; ambiguous USER+UNTRUSTED emails; semantic inactive without extras.

**Next:** M5 SDK/policy/confirm; then reproducible benchmarks before any research claims.
