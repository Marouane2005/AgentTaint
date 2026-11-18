"""Fixture-backed http.get / http.post (no outbound network)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


class MockHttpBackend:
    def __init__(self) -> None:
        self.gets: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []
        self.fixtures: dict[str, str] = {
            "https://example.com/": "<html>ok</html>",
            "http://127.0.0.1/health": "ok",
        }

    def get(self, url: str) -> dict[str, Any]:
        record = {"url": url, "method": "GET"}
        self.gets.append(record)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return {"status": 400, "url": url, "body": "unsupported scheme"}
        body = self.fixtures.get(url, f"mock-body-for:{url}")
        return {"status": 200, "url": url, "body": body, "network": False}

    def post(self, url: str, body: str = "", content: str = "") -> dict[str, Any]:
        payload = body or content
        record = {"url": url, "method": "POST", "body": payload}
        self.posts.append(record)
        return {
            "status": 200,
            "url": url,
            "echo": payload,
            "network": False,
        }

    def list_tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "http.get",
                "description": "Fetch a URL via the local mock HTTP layer (no network).",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
            {
                "name": "http.post",
                "description": "POST to a URL via the local mock HTTP layer (no network).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "body": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["url"],
                },
            },
        ]
