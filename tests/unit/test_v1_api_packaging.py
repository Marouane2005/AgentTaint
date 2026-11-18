"""Control plane: bundled UI serving, security headers, live proxy database."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_ui_directory_requires_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agenttaint_api import app as appmod

    monkeypatch.setenv("AGENTTAINT_UI_DIR", str(tmp_path))
    assert appmod.ui_directory() is None
    (tmp_path / "index.html").write_text("<html>ok</html>")
    assert appmod.ui_directory() == tmp_path


def test_security_headers_on_api() -> None:
    from agenttaint_api.app import app

    res = TestClient(app).get("/api/v1/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_live_state_reads_proxy_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agenttaint_api import state

    url = f"sqlite+pysqlite:///{tmp_path / 'shared.db'}"
    monkeypatch.setenv("AGENTTAINT_DATABASE_URL", url)
    assert state.live_database_url() == url
    live = state.create_live_state(url)
    assert live.session.mode == "live"
    assert live.overview()["decisions"]["total"] == 0


def test_memory_database_is_not_live(monkeypatch: pytest.MonkeyPatch) -> None:
    from agenttaint_api import state

    monkeypatch.setenv("AGENTTAINT_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    assert state.live_database_url() == ""


def test_demo_seed_refused_when_live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agenttaint_api.app import app

    monkeypatch.delenv("AGENTTAINT_DASHBOARD_TOKEN", raising=False)
    monkeypatch.setenv("AGENTTAINT_API_AUTH", "off")
    monkeypatch.setenv("AGENTTAINT_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'l.db'}")
    client = TestClient(app)
    assert client.post("/api/v1/demo/seed").status_code == 409
    assert client.post("/api/v1/session/clear").status_code == 409
