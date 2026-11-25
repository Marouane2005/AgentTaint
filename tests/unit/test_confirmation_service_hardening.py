"""In-memory ConfirmationService: dedupe, per-agent cap, release, token requirement, races."""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from agenttaint_agent_sdk.confirmation import (
    ConfirmationError,
    ConfirmationQueueFull,
    ConfirmationService,
    ConfirmationStatus,
)
from agenttaint_core.schemas import RiskTier

SECRET = "s" * 40


def _req(svc: ConfirmationService, to: str = "a@corp.example", agent: str = "agent_a", **kw):
    return svc.request(
        tool="email.send",
        arguments={"to": to},
        agent_id=agent,
        risk_tier=RiskTier.HIGH,
        explanation="x",
        **kw,
    )


def _consume(svc, rec, token, to="a@corp.example", agent="agent_a", **kw):
    return svc.consume(
        confirmation_id=rec.confirmation_id,
        tool="email.send",
        arguments={"to": to},
        agent_id=agent,
        approval_token=token,
        **kw,
    )


def test_identical_retry_reuses_the_open_request() -> None:
    svc = ConfirmationService(secret=SECRET)
    assert _req(svc).confirmation_id == _req(svc).confirmation_id
    assert _req(svc, to="b@corp.example").confirmation_id != _req(svc).confirmation_id


def test_different_provenance_context_is_a_different_request() -> None:
    svc = ConfirmationService(secret=SECRET)
    a = _req(svc, provenance_context_hash="h1")
    b = _req(svc, provenance_context_hash="h2")
    assert a.confirmation_id != b.confirmation_id


def test_pending_queue_is_capped_per_agent_only() -> None:
    svc = ConfirmationService(secret=SECRET, max_pending_per_agent=3)
    for i in range(3):
        _req(svc, to=f"u{i}@corp.example")
    with pytest.raises(ConfirmationQueueFull):
        _req(svc, to="overflow@corp.example")
    assert _req(svc, to="u0@corp.example")  # an existing open request is still returned
    assert _req(svc, to="other@corp.example", agent="agent_b")  # other agents unaffected


def test_expired_pending_requests_free_capacity() -> None:
    svc = ConfirmationService(secret=SECRET, max_pending_per_agent=1)
    first = _req(svc, ttl=timedelta(seconds=-1))
    second = _req(svc, to="b@corp.example")
    assert second.confirmation_id != first.confirmation_id
    assert svc.get(first.confirmation_id).status == ConfirmationStatus.EXPIRED


def test_missing_or_wrong_token_is_rejected_and_does_not_consume() -> None:
    svc = ConfirmationService(secret=SECRET)
    rec = _req(svc)
    token = svc.approve(rec.confirmation_id).approval_token
    for bad in (None, "", "forged"):
        with pytest.raises(ConfirmationError):
            _consume(svc, rec, bad)
    assert svc.get(rec.confirmation_id).status == ConfirmationStatus.APPROVED
    _consume(svc, rec, token)
    with pytest.raises(ConfirmationError):
        _consume(svc, rec, token)  # single use


def test_release_only_undoes_a_consume_before_expiry() -> None:
    svc = ConfirmationService(secret=SECRET)
    rec = _req(svc)
    assert svc.release(rec.confirmation_id) is False  # pending
    token = svc.approve(rec.confirmation_id).approval_token
    assert svc.release(rec.confirmation_id) is False  # approved, not consumed
    _consume(svc, rec, token)
    assert svc.release(rec.confirmation_id) is True
    _consume(svc, rec, token)  # usable again, exactly once
    assert svc.release("missing") is False


def test_concurrent_identical_requests_create_one_record() -> None:
    svc = ConfirmationService(secret=SECRET)
    ids: list[str] = []
    barrier = threading.Barrier(16)

    def go() -> None:
        barrier.wait()
        ids.append(_req(svc).confirmation_id)

    threads = [threading.Thread(target=go) for _ in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(ids)) == 1


def test_concurrent_requests_never_exceed_the_cap() -> None:
    svc = ConfirmationService(secret=SECRET, max_pending_per_agent=5)
    outcomes: list[str] = []
    barrier = threading.Barrier(20)

    def go(i: int) -> None:
        barrier.wait()
        try:
            _req(svc, to=f"u{i}@corp.example")
            outcomes.append("ok")
        except ConfirmationQueueFull:
            outcomes.append("full")

    threads = [threading.Thread(target=go, args=(i,)) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert outcomes.count("ok") == 5 and outcomes.count("full") == 15
