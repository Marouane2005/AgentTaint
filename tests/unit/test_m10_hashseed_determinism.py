"""FixtureEmbeddingBackend must be stable across PYTHONHASHSEED values."""

from __future__ import annotations

import hashlib

from agenttaint_reconstruction.semantic import FixtureEmbeddingBackend


def test_fixture_embedding_uses_sha256_not_salted_hash() -> None:
    backend = FixtureEmbeddingBackend(dim=32)
    token = "provenance"
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    expected_idx = int.from_bytes(digest[:8], "big") % 32
    vec = backend.embed([token])[0]
    assert vec[expected_idx] > 0.0
    # All other buckets zero before normalization → only one non-zero after.
    nonzero = sum(1 for v in vec if abs(v) > 1e-12)
    assert nonzero == 1


def test_fixture_embedding_stable_for_same_text() -> None:
    backend = FixtureEmbeddingBackend()
    a = backend.embed(["hello world from agenttaint"])[0]
    b = backend.embed(["hello world from agenttaint"])[0]
    assert a == b
