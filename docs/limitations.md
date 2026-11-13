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
17. **Envelope HMAC** uses a shared secret among cooperating components — not mutual TLS or per-agent asymmetric identity.  
18. **Confirmation binding** protects the exact approved argument bytes; it does not prove the human understood semantic risk.  
19. **Cedar** remains deferred; production policy authors should not assume Cedar semantics yet.  
20. **Custom benchmark ceiling:** held-out scenarios are synthetic and often expose contiguous structural identifiers; near-zero ASR there does not transfer to production agents.  
21. **Semantic ablation** in CI/benchmark uses a fixture embedder, not a calibrated production model.  
22. **AgentDojo / InjecAgent** were not run in Milestone 6 — do not cite custom numbers as those benchmarks.  
23. **No comparative claim** vs CaMeL/FIDES/CapLite/NeuroTaint without a fair shared protocol.  
24. **M7 hard adaptive splits** can still evade fixture reconstruction (CONFIRM / provenance FN); BGE helps on this corpus but costs latency/memory.  
25. **Bootstrap multi-seed** quantifies sampling uncertainty on a fixed synthetic set — not stochastic LLM variance.  
26. **AgentDojo** is installable but full free/local ASR evaluation was not completed (LLM-backed protocol).

## Operational

- Embedding model download requires network once.  
- Shell demo requires Docker; otherwise disabled.  
- Dashboard without backend shows empty states — never fabricated metrics.
