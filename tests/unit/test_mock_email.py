import pytest
from agenttaint_mock_email.backend import MockEmailBackend


def test_read_lists_fixture_inbox() -> None:
    backend = MockEmailBackend()
    result = backend.read()
    assert result["count"] >= 2
    bodies = " ".join(m["body"] for m in result["messages"])
    assert "attacker@example.com" in bodies


def test_send_records_outbox_without_network() -> None:
    backend = MockEmailBackend(inbox=[])
    sent = backend.send(to="bob@corp.example", subject="hi", body="hello")
    assert sent["status"] == "sent"
    assert len(backend.sent) == 1
    assert backend.sent[0].to == "bob@corp.example"


def test_send_rejects_invalid_recipient() -> None:
    backend = MockEmailBackend(inbox=[])
    with pytest.raises(ValueError):
        backend.send(to="not-an-email")
