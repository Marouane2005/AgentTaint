from agenttaint_core.hashing import content_hash, redact_sensitive


def test_content_hash_stable() -> None:
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("world")


def test_content_hash_bytes_matches_str() -> None:
    assert content_hash("abc") == content_hash(b"abc")


def test_redact_email_and_url() -> None:
    text = "Send to attacker@example.com via https://evil.example/exfil now"
    redacted = redact_sensitive(text)
    assert "attacker@example.com" not in redacted
    assert "https://evil.example/exfil" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_URL]" in redacted
