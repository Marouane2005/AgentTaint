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
12. **Cross-agent transfer** only preserves lineage among AgentTaint-aware callers using `transfer_to_agent` with verified parent ids.  
13. **Reconstruction is not causation:** lexical/structural/semantic support levels are not calibrated probabilities; attached edges are always INFERRED.  
14. **Adaptive evasion:** splitting identifiers across messages, novel encodings, and heavy paraphrase can yield UNKNOWN / false negatives.  
15. **Ambiguous structural values** (same email in USER and UNTRUSTED text) can produce multiple INFERRED matches — policy must still require explicit authorization.  
16. **Semantic embeddings** are optional; default CI uses a fixture embedder or disables the channel.

## Operational

- Embedding model download requires network once.  
- Shell demo requires Docker; otherwise disabled.  
- Dashboard without backend shows empty states — never fabricated metrics.
