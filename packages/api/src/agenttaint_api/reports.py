"""Load measured benchmark reports from disk.

Full JSON artifacts are gitignored (they are large). The committed markdown
summaries are the same numbers the report writer emitted. This module reads
JSON when it is present and otherwise parses those markdown tables. It never
fills in a metric that is not in the file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_HEADER = re.compile(r"^- \*\*([a-z_]+):\*\* `([^`]*)`", re.MULTILINE)
_NA = {"n/a", "na", "—", "-", ""}

# Markdown column -> field the dashboard already renders.
_COLUMNS = {
    "config": "config",
    "n": "n_scenarios",
    "ASR": "asr",
    "FNR": "fnr",
    "FPR_block": "fpr_block",
    "FPR_confirm": "fpr_confirm",
    "utility": "utility",
    "P": "provenance_precision",
    "R": "provenance_recall",
    "F1": "provenance_f1",
    "lat_med_ms": "latency_ms_median",
    "lat_p95_ms": "latency_ms_p95",
}


def _metric(cell: str) -> int | float | None:
    text = cell.strip()
    if text.lower() in _NA:
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return float(text)


def _table(section: str) -> dict[str, dict[str, Any]]:
    """Parse the first markdown table in a section into {config: metrics}."""
    rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(rows) < 2:
        return {}
    headers = [cell.strip() for cell in rows[0].strip("|").split("|")]
    out: dict[str, dict[str, Any]] = {}
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        raw = dict(zip(headers, cells, strict=True))
        name = raw.get("config", "").strip()
        if not name or set(name) <= {"-"}:
            continue
        metrics: dict[str, Any] = {}
        for column, key in _COLUMNS.items():
            if column == "config" or column not in raw:
                continue
            metrics[key] = _metric(raw[column])
        out[name] = metrics
    return out


def _section_map(text: str) -> dict[str, str]:
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    found: dict[str, str] = {}
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        found[title.strip()] = body
    return found


def parse_markdown_report(text: str, *, path: str) -> dict[str, Any] | None:
    """Return a dashboard report dict, or None when the file has no defense table."""
    headers = {key: value for key, value in _HEADER.findall(text)}
    sections = _section_map(text)
    per_defense = {}
    per_ablation = {}
    limitations: list[str] = []
    for title, body in sections.items():
        if title.startswith("Per-defense"):
            per_defense = _table(body)
        elif title.startswith("Reconstruction ablations"):
            per_ablation = _table(body)
        elif title.startswith("Limitations"):
            limitations = [
                line[2:].strip()
                for line in body.splitlines()
                if line.startswith("- ") and line[2:].strip()
            ]
    if not per_defense:
        return None
    return {
        "path": path,
        "report_id": headers.get("report_id") or path,
        "dataset_version": headers.get("dataset_version"),
        "seed": headers.get("seed"),
        "semantic_backend": headers.get("semantic_backend"),
        "split": "test",
        "per_defense": per_defense,
        "per_ablation": per_ablation,
        "limitations": limitations,
        "created_at": headers.get("created_at"),
        "artifact": "markdown",
        "artifact_note": (
            "Numbers are read from the committed markdown summary. "
            "The full JSON artifact is not in this checkout."
        ),
    }


def _from_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw.get("per_defense"):
        return None
    return {
        "path": path.name,
        "report_id": str(raw.get("report_id") or path.name),
        "dataset_version": raw.get("dataset_version"),
        "seed": raw.get("seed"),
        "semantic_backend": (raw.get("config") or {}).get("semantic_backend"),
        "split": raw.get("split"),
        "per_defense": raw.get("per_defense") or {},
        "per_ablation": raw.get("per_ablation") or {},
        "limitations": raw.get("limitations") or [],
        "created_at": raw.get("created_at"),
        "artifact": "json",
        "artifact_note": "Numbers are read from the JSON report on disk.",
    }


def load_report_files(directory: Path) -> list[dict[str, Any]]:
    """JSON first, then markdown. A report id already loaded from JSON is kept."""
    if not directory.is_dir():
        return []
    by_id: dict[str, dict[str, Any]] = {}
    json_paths = sorted(
        directory.glob("report_test_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    md_paths = sorted(
        directory.glob("report_test_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in json_paths:
        parsed = _from_json(path)
        if parsed is None:
            continue
        by_id.setdefault(str(parsed["report_id"]), parsed)
    for path in md_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        parsed = parse_markdown_report(text, path=path.name)
        if parsed is None:
            continue
        by_id.setdefault(str(parsed["report_id"]), parsed)
    reports = list(by_id.values())
    preferred: list[dict[str, Any]] = []
    for key in ("fixture", "bge", "experiment"):
        for report in reports:
            if key in str(report["path"]) and report not in preferred:
                preferred.append(report)
    ordered = preferred + [report for report in reports if report not in preferred]
    return ordered
