# Provenance Reconstruction Engine (Milestone 4)

## Purpose

Estimate *possible* relationships between tool-call arguments and previously observed spans after summarization, paraphrase, memory, or cross-agent transfer.

**Reconstruction does not prove causation.**

## Channels

| Channel | Method | Notes |
|---------|--------|-------|
| Lexical | Exact/normalized substring, token Jaccard, bigram Jaccard | Brittle to heavy paraphrase |
| Structural | Emails, URLs, IPs, paths, shell tokens + normalization | Strong for authority arguments; some obfuscation handled (`[at]`/`[dot]`) |
| Semantic | Optional local embeddings (SentenceTransformers / `bge-small-en-v1.5`) | Inactive unless `[semantic]` extra installed; tests use fixture embedder |
| Explicit | SDK/graph lineage flags supplied by caller | Separate from reconstruction edges |

## Epistemic rules

1. Attached reconstruction spans are always **`INFERRED`**.
2. Insufficient evidence → effective status **`UNKNOWN`** (no edge attached).
3. `ArgumentEvidence.confidence` is **always `null`** until calibrated evaluation exists.
4. Support levels (`NONE`/`WEAK`/`MODERATE`/`STRONG`) are ordinal scrutiny hints — **not** probabilities.
5. Ablation modes: `lexical`, `structural`, `semantic`, `explicit`, `lexical_structural`, `combined`.

## API sketch

```python
engine = ReconstructionEngine(registry, embedding_backend=None)  # or FixtureEmbeddingBackend()
result = engine.reconstruct_argument(
    argument_name="to",
    argument_value="attacker@example.com",
    candidates=[CandidateRecord(span_id=..., text=...)],
    ablation=AblationMode.COMBINED,
    attach=True,
)
# result.inferred_spans[*].provenance_status == INFERRED
```

Candidate texts are supplied via a corpus so the provenance DB can keep redacted content.

## Known failure modes (documented, tested)

- Recipient identity **split across messages** often yields UNKNOWN / weak evidence.
- Heavy paraphrase without retained structural values may miss with lexical-only.
- Ambiguous emails present in both USER and UNTRUSTED sources produce **multiple INFERRED matches** — policy must not treat that as authorization.
- Semantic channel absent in default CI (no mandatory model download).

## Optional semantic install

```bash
pip install -e "./packages/reconstruction[semantic]"
```

Requires disk/RAM for the embedding model; CPU-only is supported. Core tests never require it.

## What this is not

- Not a prompt-injection classifier
- Not CapLite request grounding (that is policy)
- Not NeuroTaint offline causal LLM auditing
- Not a calibrated probability model of influence
