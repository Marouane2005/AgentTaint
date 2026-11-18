"""Locate the default policy and trust registry files.

Resolution order for ``default_policy_file(name)``:

1. ``$AGENTTAINT_POLICY_DIR/<name>`` when that variable is set;
2. ``policies/<name>`` in a source checkout (development layout);
3. the copy shipped inside this package (wheel installs).

The shipped copies are kept byte-identical to ``policies/`` by a unit test.
"""

from __future__ import annotations

import os
from pathlib import Path

POLICY_FILE = "provenance_policy.yaml"
TRUST_REGISTRY_FILE = "trust_registry.yaml"

_PACKAGE_DEFAULTS = Path(__file__).resolve().parent / "defaults"


def source_checkout_root() -> Path | None:
    """Return the repository root when running from a source checkout."""
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "policies").is_dir() and (candidate / "packages").is_dir():
        return candidate
    return None


def packaged_default(name: str) -> Path:
    return _PACKAGE_DEFAULTS / name


def default_policy_file(name: str) -> Path:
    override = os.environ.get("AGENTTAINT_POLICY_DIR", "").strip()
    if override:
        return Path(override) / name
    root = source_checkout_root()
    if root is not None and (root / "policies" / name).is_file():
        return root / "policies" / name
    return packaged_default(name)
