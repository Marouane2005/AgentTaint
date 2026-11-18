# Related Work — AgentTaint Literature Review

**Status:** Living — M14 reaffirms no primacy claims without shared protocols  
**Date:** 2026-11-18  
**Rule:** Do not claim AgentTaint is the first provenance / taint / IFC system for AI agents. Novelty must be established experimentally.

Benchmarks (AgentDojo, InjecAgent), classic taint tracking and IFC foundations
are covered with references in [technical_report.md](technical_report.md) §4.

---

## Summary comparison

| System | Mode | Core mechanism | Semantic transforms | Multi-agent | MCP boundary | Guarantee style |
|--------|------|----------------|---------------------|-------------|--------------|-----------------|
| **CaMeL** | Online enforcement | Privileged planner + capabilities + custom interpreter | Explicit dataflow only | Limited / single-plan | No (general tools) | Control/data-flow integrity when plan is trusted |
| **FIDES** | Online IFC | Integrity + confidentiality labels, hide/reveal | Label join on instrumented paths | Framework-scoped | No (Agent Framework middleware) | Noninterference (integrity) under correct labeling |
| **CapLite** | Online enforcement | Request grounding of authority args; commit writes before reads | N/A (blocks ungrounded writes) | No | No | Write integrity by construction |
| **NeuroTaint** | Offline audit | Semantic + causal + persistent taint reconstruction | Yes (core claim) | Cross-session memory | No | Detection / evidence, not live blocking |
| **AgentTaint (proposed)** | Online MCP proxy + reconstruction | Explicit provenance graph + inferred evidence + risk policy | Yes (instrumented + reconstructed) | Yes (authenticated envelopes) | Yes | Fail-closed policy on high-risk sinks; inferred ≠ known |

---

## CaMeL — Capabilities for Machine Learning

**Citation:** Debenedetti et al., *Defeating Prompt Injections by Design* (arXiv:2503.18813). Code: `google-research/camel-prompt-injection`.

### Research question
Can a system layer around an LLM agent enforce control-flow and data-flow policies so that untrusted tool outputs cannot hijack tool selection or exfiltrate private data, without trusting the underlying model?

### Architecture
- **Privileged LLM** extracts a plan / control flow from the *trusted* user query.
- **Quarantined LLM** processes untrusted data without deciding control flow.
- **Custom interpreter** executes the plan and maintains a data-flow graph over values.
- **Capabilities** (security metadata) on values encode origins and allowed uses; checked at tool invocation.

### Security assumptions
- The user query is trusted for control-flow extraction.
- The interpreter and capability enforcement are correct.
- Policies exist for tools and data sharing.

### Strengths
- Strong systems-security framing (CFI / IFC / capabilities).
- Demonstrated on AgentDojo (~77% tasks with provable security vs ~84% undefended utility).
- Does not require fine-tuning the base model.

### Limitations
- Requires codifying security policies; usability burden.
- Utility loss vs undefended agents.
- Plan extraction can fail; side channels remain.
- Not MCP-native; not designed for reconstructing influence after *uninstrumented* paraphrases across independently running agents.

### Relation to AgentTaint
CaMeL is an **enforcement-first** design with *explicit* capability tracking inside a custom runtime. AgentTaint targets the **MCP proxy boundary** and adds **probabilistic reconstruction** when instrumentation is incomplete. AgentTaint should **not** claim stronger guarantees than CaMeL on fully instrumented paths; CaMeL’s guarantees are stronger when its assumptions hold.

---

## FIDES — Flow Integrity Deterministic Enforcement System

**Citation:** Costa et al., *Securing AI Agents with Information-Flow Control* (arXiv:2505.23643). Tutorial: `microsoft/fides`. Shipping experimentally in Microsoft Agent Framework (`agent_framework.security`).

### Research question
What planner designs and IFC instrumentation yield deterministic integrity/confidentiality guarantees for agent tool use, and what is the security–utility trade-off?

### Architecture
- Dual-axis labels: **integrity** (trusted / untrusted) and **confidentiality** (public / private / user_identity).
- Middleware propagates the most restrictive labels through tool I/O.
- Policy enforcement before sensitive tools.
- **Hide** untrusted content behind variables; **reveal** via quarantined LLM + constrained decoding / typed extraction.

### Security assumptions
- All relevant content is labeled at ingress.
- Middleware sees every tool call on the instrumented planner path.
- Combining labels via lattice join is sound for the stated policies.

### Strengths
- Clear formal model of planner IFC.
- Deterministic enforcement (not classifier-based).
- Practical hide/reveal primitives that preserve utility better than always-taint-everything.
- AgentDojo evaluation with security guarantees on completed tasks.

### Limitations
- Guarantees depend on complete instrumentation of the planner.
- Cross-process / cross-vendor agents can lie about labels without a shared trust root.
- Does not treat *inferred* provenance after paraphrasing as a first-class research object with ablation of evidence channels.
- Not an MCP proxy.

### Relation to AgentTaint
FIDES is the closest **online IFC** peer. AgentTaint overlaps on label propagation and policy gates. Distinct emphasis for investigation: **MCP enforcement**, **KNOWN / INFERRED / UNKNOWN** epistemology, **multi-signal reconstruction** with mandatory ablation, and **cross-agent authenticated provenance envelopes**. Claims of superiority require head-to-head experiments; conceptual overlap is substantial.

---

## CapLite

**Citation:** *CapLite: Prompt-Injection Defense for Small Language Model Agents without Model-Written Security Artifacts* (arXiv:2611.17115).

### Research question
Can SLM agents be defended without trusting the model to write security artifacts (programs, privilege policies, dependency graphs)?

### Architecture
- Policy derived from **tool schemas** (read vs write verbs; authority arguments).
- Planner commits write calls **before** reading tool results.
- Mediator admits a write only if every **authority argument** (recipient, amount, URL, object id, …) is **stated in the user request** (or confirmed).

### Security assumptions
- User request is the sole authority for write destinations/objects.
- Tool schema classification is correct.
- Writes cannot be added after untrusted reads.

### Strengths
- Strong write-integrity properties by construction.
- Reports 0 successful attacks across 13,935 attacked AgentDojo episodes.
- Better token efficiency than CaMeL-style artifact writing for SLMs.
- Avoids model-written security artifacts (important negative result about Progent / IPIGuard / DRIFT / CaMeL programs on SLMs).

### Limitations
- Utility constrained: many legitimate tasks need destinations that appear only in tool data (e.g., “email Bob what he asked for”).
- Not a general provenance system; does not explain *how* untrusted content influenced an argument—it simply forbids ungrounded authority args.
- Multi-agent / memory / paraphrase tracking is out of scope.

### Relation to AgentTaint
CapLite’s **request grounding** is a policy pattern AgentTaint should encode as a first-class rule (USER-authorized destinations). AgentTaint aims for finer utility on tasks CapLite would block, by allowing high-risk actions when **explicit provenance + user authorization** justify them—at the cost of weaker absolute guarantees and dependence on reconstruction quality.

---

## NeuroTaint

**Citation:** *Ghost in the Agent: Redefining Information Flow Tracking for LLM Agents* (arXiv:2604.23374).

### Research question
How should taint analysis be redefined for LLM agents where propagation is semantic, causal, and persistent across memory—not exact string flow?

### Architecture
- **Offline** auditor over execution traces.
- Reconstructs source→sink provenance via semantic evidence, causal reasoning, and cross-session persistence.
- Evaluated primarily on **TaintBench** (400 scenarios, 20 frameworks); also InjecAgent / ToolEmu transfer checks.
- Reports high F1 for propagation detection vs an IFC-style FIDES baseline on TaintBench.

### Security assumptions
- Traces are available and roughly faithful.
- Offline analysis latency is acceptable (audit, not necessarily inline block).
- Semantic/causal signals correlate with true influence (imperfect).

### Strengths
- Directly addresses semantic transformation and memory persistence—the hard problem AgentTaint also targets.
- Explicit contrast with IFC-style baselines that miss implicit flows.
- Benchmark dedicated to provenance detection (TaintBench).

### Limitations
- Offline detection ≠ online enforcement at a tool boundary.
- Auditor-side LLM queries introduce cost and their own attack surface.
- Multi-agent authenticated lineage and MCP proxy integration are not the primary artifact.
- “First comprehensive taint tracking framework” claim in the paper should be treated carefully; AgentTaint must not copy that claim.

### Relation to AgentTaint
NeuroTaint is the closest peer on **reconstruction**. AgentTaint’s potential differentiation to *investigate* (not assert a priori):
1. **Online** MCP proxy enforcement using reconstruction evidence.
2. Strict separation of **KNOWN vs INFERRED vs UNKNOWN** with fail-closed policy for high-risk sinks.
3. **Authenticated cross-agent envelopes** and shared provenance service.
4. Research methodology: mandatory **ablation** of lexical / semantic / structural / explicit channels.
5. Risk-tiered decisions (ALLOW / BLOCK / CONFIRM) with auditable Cedar or equivalent policies.

Whether these yield a scientifically meaningful contribution is an **empirical** question.

---

## AgentDojo

**Citation:** Debenedetti et al., NeurIPS 2024 Datasets & Benchmarks. Site: https://agentdojo.spylab.ai/

### Purpose
Dynamic environment to evaluate prompt-injection attacks and defenses for tool-using LLM agents (97 tasks, 629 security test cases across email, banking, travel, etc.).

### Relevance
Primary external benchmark for CaMeL, CapLite, FIDES, and planned AgentTaint evaluation. Measure ASR, utility, and security–utility trade-offs under official protocols. Document any adapter changes.

### Limitations for AgentTaint
Not designed for multi-agent provenance ablation. Cross-agent transformation scenarios need a **custom** benchmark in addition to AgentDojo.

---

## InjecAgent

**Citation:** Zhan et al., *InjecAgent* (arXiv:2403.02691). ~1,054 cases; 17 user tools / 62 attacker tools; direct harm vs data exfiltration.

### Purpose
Benchmark indirect prompt injection in tool-integrated agents (often single-turn simulated tool output).

### Relevance
Transfer evaluation for AgentTaint’s proxy + policy stack. Do not silently alter tasks. Note: labels are unsafe-action oriented, not pure provenance labels (NeuroTaint makes the same caveat).

---

## Other relevant lines of work (brief)

| Work | Relevance |
|------|-----------|
| Dual LLM / quarantined LLM (Willison et al.) | Architectural pattern reused by CaMeL/FIDES |
| Traditional IFC / taint (Denning, language-based security) | Conceptual ancestor; fails on NL transforms |
| Prompt-injection classifiers / Spotlighting / delimiters | Content-based defenses AgentTaint deliberately does *not* rely on exclusively |
| Proof-carrying / unprunable ancestry sketches | Motivates authenticated lineage; cryptographic PCIF is out of MVP scope |
| ToolEmu | Additional unsafe-agent evaluation environment |

---

## Honest novelty assessment

**Not novel by itself:** provenance labels, IFC for agents, MCP security proxies, request grounding, offline semantic taint.

**Hypothesis to test (not claim):** Combining (a) instrumented multi-agent provenance graphs, (b) multi-signal reconstruction with explicit uncertainty, and (c) risk-sensitive online enforcement at an MCP proxy yields better *security–utility–explainability* on transformed and cross-agent attacks than CapLite-style grounding alone, FIDES-style coarse labels alone, or NeuroTaint-style offline audit alone.

**If experiments fail to show this,** document that result. The project remains valuable as a reproducible MCP-native IFC + reconstruction platform.

### M9 update

Custom synthetic results (M6/M7) do **not** establish primacy vs CaMeL/FIDES/CapLite/NeuroTaint. AgentDojo and InjecAgent remain **not evaluated** for full ASR under free/local constraints (`docs/external_benchmarks_feasibility.md`). Any public write-up must keep that separation explicit.
