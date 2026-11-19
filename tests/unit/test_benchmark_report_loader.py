"""Benchmark Lab must read committed markdown when JSON artifacts are absent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agenttaint_api import state
from agenttaint_api.reports import load_report_files, parse_markdown_report


def test_committed_markdown_reports_are_visible() -> None:
    body = state.load_benchmark_summary()
    assert body["available"] is True
    assert body["scenarios"]["catalog_count"] >= 20
    assert body["scenarios"]["counts"]["test"] >= 60
    paths = {report["path"] for report in body["reports"]}
    assert "report_test_m12_069d5298.md" in paths
    m12 = next(r for r in body["reports"] if r["path"] == "report_test_m12_069d5298.md")
    assert m12["artifact"] == "markdown"
    assert m12["dataset_version"] == "2026.11.18-m12.1"
    combined = m12["per_defense"]["combined:combined"]
    assert combined["n_scenarios"] == 68
    assert combined["asr"] == 0.0
    assert combined["utility"] == 1.0
    undefended = m12["per_defense"]["undefended"]
    assert undefended["asr"] == 1.0
    assert m12["per_ablation"]["semantic"]["provenance_recall"] == pytest.approx(0.118)
    assert any("synthetic" in item.lower() for item in m12["limitations"])


def test_json_report_wins_over_markdown_with_the_same_id(tmp_path: Path, monkeypatch) -> None:
    report_id = "11111111-2222-3333-4444-555555555555"
    markdown = "\n".join(
        [
            "# AgentTaint Benchmark Report (`test`)",
            "",
            f"- **report_id:** `{report_id}`",
            "- **dataset_version:** `from-markdown`",
            "- **seed:** `1`",
            "",
            "## Per-defense metrics",
            "",
            "| config | n | ASR | utility |",
            "| --- | --- | --- | --- |",
            "| undefended | 3 | 1.000 | 1.000 |",
            "",
        ]
    )
    (tmp_path / "report_test_fixture_aaaaaaaa.md").write_text(markdown, encoding="utf-8")
    (tmp_path / "report_test_fixture_aaaaaaaa.json").write_text(
        json.dumps(
            {
                "report_id": report_id,
                "dataset_version": "from-json",
                "seed": 9,
                "split": "test",
                "config": {"semantic_backend": "fixture-hash-embedder-v1"},
                "per_defense": {"undefended": {"n_scenarios": 3, "asr": 1.0, "utility": 1.0}},
                "per_ablation": {},
                "limitations": ["json copy"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(state, "BENCHMARKS", tmp_path)
    body = state.load_benchmark_summary()
    assert body["available"] is True
    assert len(body["reports"]) == 1
    assert body["reports"][0]["artifact"] == "json"
    assert body["reports"][0]["dataset_version"] == "from-json"
    assert body["reports"][0]["semantic_backend"] == "fixture-hash-embedder-v1"


def test_missing_directory_stays_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(state, "BENCHMARKS", tmp_path / "absent")
    body = state.load_benchmark_summary()
    assert body["available"] is False
    assert "make benchmark" in (body["message"] or "")
    assert body["scenarios"]["catalog_count"] >= 20


def test_markdown_without_a_defense_table_is_ignored(tmp_path: Path) -> None:
    parsed = parse_markdown_report("# notes only\n\nNo table.\n", path="report_test_x.md")
    assert parsed is None
    (tmp_path / "report_test_x.md").write_text("# notes only\n", encoding="utf-8")
    assert load_report_files(tmp_path) == []
