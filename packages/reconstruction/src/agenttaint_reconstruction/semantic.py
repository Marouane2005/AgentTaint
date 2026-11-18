"""Optional semantic similarity via local embeddings.

Default install does NOT require torch / sentence-transformers.
When unavailable, semantic channel is disabled and reports as inactive.
Cosine similarity is an evidence signal, not causation probability.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SemanticScore:
    available: bool
    cosine: float | None
    model_name: str | None
    note: str


class EmbeddingBackend(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


class FixtureEmbeddingBackend:
    """Deterministic bag-of-hashed-tokens embedder for offline tests (no ML deps)."""

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    @property
    def model_name(self) -> str:
        return "fixture-hash-embedder-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            tokens = text.casefold().split()
            if not tokens:
                vectors.append(vec)
                continue
            for token in tokens:
                # Stable across PYTHONHASHSEED (stdlib hash() is salted per process).
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:8], "big") % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class SentenceTransformerBackend:
    """Lazy local SentenceTransformer backend (optional extra)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import (  # type: ignore[import-not-found,unused-ignore]
            SentenceTransformer,
        )

        self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        assert self._model is not None
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in vectors]


def try_create_default_semantic_backend() -> EmbeddingBackend | None:
    """Return SentenceTransformer backend if extras are installed; else None."""
    try:
        import sentence_transformers  # noqa: F401
        import torch  # type: ignore[import-not-found,unused-ignore]  # noqa: F401
    except ImportError:
        return None
    return SentenceTransformerBackend()


def semantic_similarity(
    query: str,
    candidate: str,
    backend: EmbeddingBackend | None,
) -> SemanticScore:
    if backend is None:
        return SemanticScore(
            available=False,
            cosine=None,
            model_name=None,
            note="semantic channel inactive (no embedding backend)",
        )
    q_vec, c_vec = backend.embed([query, candidate])
    return SemanticScore(
        available=True,
        cosine=cosine_similarity(q_vec, c_vec),
        model_name=backend.model_name,
        note="cosine similarity is an evidence signal, not causation probability",
    )
