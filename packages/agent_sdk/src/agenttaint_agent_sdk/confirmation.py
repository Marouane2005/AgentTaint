"""Confirmation binding: approval is single-use and bound to exact action context.

Binding tuple: (tool, arguments_hash, agent_id).
Replay, expiry, and argument modification after approval all fail closed.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from agenttaint_core.crypto import generate_nonce, hmac_sign, hmac_verify
from agenttaint_core.hashing import content_hash
from agenttaint_core.schemas import RiskTier


def _utcnow() -> datetime:
    return datetime.now(UTC)


def canonicalize_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, default=str)


def arguments_hash(arguments: dict[str, Any]) -> str:
    return content_hash(canonicalize_arguments(arguments))


class ConfirmationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass
class ConfirmationRecord:
    confirmation_id: str
    tool: str
    arguments_hash: str
    arguments_redacted: dict[str, Any]
    agent_id: str
    risk_tier: RiskTier
    explanation: str
    created_at: datetime
    expires_at: datetime
    status: ConfirmationStatus
    nonce: str
    approval_token: str | None = None
    policy_id: str | None = None


class ConfirmationError(PermissionError):
    pass


class ConfirmationService:
    """In-memory confirmation binder for local MVP / tests."""

    def __init__(
        self,
        *,
        secret: str,
        default_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self.secret = secret
        self.default_ttl = default_ttl
        self._records: dict[str, ConfirmationRecord] = {}

    def request(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        agent_id: str,
        risk_tier: RiskTier,
        explanation: str,
        arguments_redacted: dict[str, Any] | None = None,
        policy_id: str | None = None,
        ttl: timedelta | None = None,
    ) -> ConfirmationRecord:
        now = _utcnow()
        record = ConfirmationRecord(
            confirmation_id=str(uuid4()),
            tool=tool,
            arguments_hash=arguments_hash(arguments),
            arguments_redacted=dict(arguments_redacted or {}),
            agent_id=agent_id,
            risk_tier=risk_tier,
            explanation=explanation,
            created_at=now,
            expires_at=now + (ttl or self.default_ttl),
            status=ConfirmationStatus.PENDING,
            nonce=generate_nonce(),
            policy_id=policy_id,
        )
        self._records[record.confirmation_id] = record
        return record

    def _token_payload(self, record: ConfirmationRecord) -> str:
        return json.dumps(
            {
                "confirmation_id": record.confirmation_id,
                "tool": record.tool,
                "arguments_hash": record.arguments_hash,
                "agent_id": record.agent_id,
                "nonce": record.nonce,
                "expires_at": record.expires_at.astimezone(UTC).isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def approve(self, confirmation_id: str) -> ConfirmationRecord:
        record = self._get(confirmation_id)
        self._ensure_pending_fresh(record)
        record.status = ConfirmationStatus.APPROVED
        record.approval_token = hmac_sign(self.secret, self._token_payload(record))
        return record

    def deny(self, confirmation_id: str) -> ConfirmationRecord:
        record = self._get(confirmation_id)
        self._ensure_pending_fresh(record)
        record.status = ConfirmationStatus.DENIED
        record.approval_token = None
        return record

    def consume(
        self,
        *,
        confirmation_id: str,
        tool: str,
        arguments: dict[str, Any],
        agent_id: str,
        approval_token: str | None,
    ) -> ConfirmationRecord:
        """Validate binding and consume a single-use approval."""
        record = self._get(confirmation_id)
        now = _utcnow()
        if record.expires_at < now:
            record.status = ConfirmationStatus.EXPIRED
            raise ConfirmationError("confirmation expired")
        if record.status == ConfirmationStatus.CONSUMED:
            raise ConfirmationError("confirmation already consumed (replay)")
        if record.status == ConfirmationStatus.DENIED:
            raise ConfirmationError("confirmation was denied")
        if record.status != ConfirmationStatus.APPROVED:
            raise ConfirmationError(f"confirmation not approved ({record.status.value})")
        if record.tool != tool:
            raise ConfirmationError("confirmation tool mismatch")
        if record.agent_id != agent_id:
            raise ConfirmationError("confirmation agent mismatch")
        if record.arguments_hash != arguments_hash(arguments):
            raise ConfirmationError(
                "confirmation arguments mismatch (possible modification after approval)"
            )
        if not approval_token or not record.approval_token:
            raise ConfirmationError("missing approval token")
        if not hmac_verify(self.secret, self._token_payload(record), approval_token):
            raise ConfirmationError("invalid approval token")
        if not hmac.compare_digest(record.approval_token, approval_token):
            raise ConfirmationError("approval token mismatch")
        record.status = ConfirmationStatus.CONSUMED
        return record

    def get(self, confirmation_id: str) -> ConfirmationRecord | None:
        return self._records.get(confirmation_id)

    def _get(self, confirmation_id: str) -> ConfirmationRecord:
        record = self._records.get(confirmation_id)
        if record is None:
            raise ConfirmationError("unknown confirmation_id")
        return record

    def _ensure_pending_fresh(self, record: ConfirmationRecord) -> None:
        if record.expires_at < _utcnow():
            record.status = ConfirmationStatus.EXPIRED
            raise ConfirmationError("confirmation expired")
        if record.status != ConfirmationStatus.PENDING:
            raise ConfirmationError(f"confirmation not pending ({record.status.value})")
