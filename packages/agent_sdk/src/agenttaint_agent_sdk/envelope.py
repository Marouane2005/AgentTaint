"""Authenticated provenance envelopes for cross-agent transfer.

Guarantees (cooperating agents sharing a secret + provenance registry):
- Tampered envelopes fail HMAC verification
- Replayed nonces are rejected
- Stale envelopes outside max_age are rejected
- Claimed parent span ids must exist in the shared registry

Does NOT guarantee provenance for agents outside the trust root / without SDK use.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from agenttaint_core.crypto import generate_nonce, hmac_sign, hmac_verify
from agenttaint_core.hashing import content_hash
from agenttaint_provenance.registry import ProvenanceRegistry
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EnvelopeError(ValueError):
    """Raised when an envelope fails authentication or validation."""


class ProvenanceEnvelope(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    sender_agent: str
    recipient_agent: str
    content: str
    content_hash: str
    parent_span_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    nonce: str = Field(default_factory=generate_nonce)
    signature: str = ""

    def canonical_payload(self) -> str:
        body = {
            "message_id": self.message_id,
            "sender_agent": self.sender_agent,
            "recipient_agent": self.recipient_agent,
            "content_hash": self.content_hash,
            "parent_span_ids": list(self.parent_span_ids),
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "nonce": self.nonce,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def sign(self, secret: str) -> ProvenanceEnvelope:
        if content_hash(self.content) != self.content_hash:
            raise EnvelopeError("content_hash does not match content")
        sig = hmac_sign(secret, self.canonical_payload())
        return self.model_copy(update={"signature": sig})


class NonceStore:
    """In-memory nonce replay cache with optional TTL pruning."""

    def __init__(self) -> None:
        self._seen: dict[str, datetime] = {}

    def seen(self, nonce: str) -> bool:
        return nonce in self._seen

    def remember(self, nonce: str, *, when: datetime | None = None) -> None:
        self._seen[nonce] = when or _utcnow()

    def prune(self, older_than: timedelta) -> None:
        cutoff = _utcnow() - older_than
        self._seen = {n: t for n, t in self._seen.items() if t >= cutoff}


class EnvelopeVerifier:
    def __init__(
        self,
        *,
        secret: str,
        registry: ProvenanceRegistry,
        nonce_store: NonceStore | None = None,
        max_age: timedelta = timedelta(minutes=10),
        allowed_agents: set[str] | None = None,
    ) -> None:
        self.secret = secret
        self.registry = registry
        self.nonce_store = nonce_store or NonceStore()
        self.max_age = max_age
        self.allowed_agents = allowed_agents

    def create(
        self,
        *,
        sender_agent: str,
        recipient_agent: str,
        content: str,
        parent_span_ids: list[str],
    ) -> ProvenanceEnvelope:
        if self.allowed_agents is not None and sender_agent not in self.allowed_agents:
            raise EnvelopeError(f"sender agent not allowed: {sender_agent}")
        for span_id in parent_span_ids:
            if self.registry.store.get_span(span_id) is None:
                raise EnvelopeError(f"cannot seal envelope: unknown parent {span_id}")
        env = ProvenanceEnvelope(
            sender_agent=sender_agent,
            recipient_agent=recipient_agent,
            content=content,
            content_hash=content_hash(content),
            parent_span_ids=list(parent_span_ids),
        )
        return env.sign(self.secret)

    def verify(self, envelope: ProvenanceEnvelope | dict[str, Any]) -> ProvenanceEnvelope:
        env = (
            envelope
            if isinstance(envelope, ProvenanceEnvelope)
            else ProvenanceEnvelope.model_validate(envelope)
        )
        if not env.signature:
            raise EnvelopeError("missing signature")
        if not hmac_verify(self.secret, env.canonical_payload(), env.signature):
            raise EnvelopeError("invalid envelope signature")
        if content_hash(env.content) != env.content_hash:
            raise EnvelopeError("content tampered (hash mismatch)")
        created = env.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age = _utcnow() - created.astimezone(UTC)
        if age > self.max_age or age < timedelta(seconds=-30):
            raise EnvelopeError("envelope expired or timestamp skew too large")
        if self.nonce_store.seen(env.nonce):
            raise EnvelopeError("replayed envelope nonce")
        if self.allowed_agents is not None:
            if env.sender_agent not in self.allowed_agents:
                raise EnvelopeError(f"unknown sender agent: {env.sender_agent}")
            if env.recipient_agent not in self.allowed_agents:
                raise EnvelopeError(f"unknown recipient agent: {env.recipient_agent}")
        for span_id in env.parent_span_ids:
            if self.registry.store.get_span(span_id) is None:
                raise EnvelopeError(f"missing parent span in registry: {span_id}")
        # Mark nonce only after all checks pass.
        self.nonce_store.remember(env.nonce)
        return env

    def accept(
        self,
        envelope: ProvenanceEnvelope | dict[str, Any],
        *,
        expected_recipient: str,
    ) -> Any:
        """Verify envelope and record a TRANSFERRED_TO_AGENT span for the recipient."""
        env = self.verify(envelope)
        if env.recipient_agent != expected_recipient:
            raise EnvelopeError(
                f"recipient mismatch: envelope={env.recipient_agent} "
                f"expected={expected_recipient}"
            )
        if not env.parent_span_ids:
            gap, _ = self.registry.record_gap(
                reason="envelope_without_parents",
                output_content=env.content,
                claimed_parent_ids=[],
                agent_id=expected_recipient,
            )
            return gap
        span, _ = self.registry.transfer_to_agent(
            sender_agent=env.sender_agent,
            recipient_agent=expected_recipient,
            content=env.content,
            parent_span_ids=env.parent_span_ids,
        )
        # Annotate envelope message id for audit correlation.
        span.metadata["envelope_message_id"] = env.message_id
        return span
