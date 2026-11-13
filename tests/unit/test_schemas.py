import pytest
from agenttaint_core.schemas import (
    SCHEMA_VERSION,
    Origin,
    ProvenanceSpan,
    ProvenanceStatus,
    SpanKind,
)
from pydantic import ValidationError


def test_span_defaults_known() -> None:
    span = ProvenanceSpan(
        origin=Origin.UNTRUSTED_TOOL,
        content_hash="a" * 64,
        kind=SpanKind.TOOL_RESULT,
    )
    assert span.provenance_status == ProvenanceStatus.KNOWN
    assert span.schema_version == SCHEMA_VERSION
    assert span.parent_ids == []


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ProvenanceSpan(
            origin=Origin.UNKNOWN,
            content_hash="b" * 64,
            provenance_status=ProvenanceStatus.INFERRED,
            confidence=1.5,
        )
