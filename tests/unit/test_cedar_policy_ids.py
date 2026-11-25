"""Static policy-id hygiene. Runs without cedarpy, so it works in minimal environments."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "packages/policy/src/agenttaint_policy"
CEDAR_IDS = re.findall(r'@id\("([^"]+)"\)', (POLICY_DIR / "cedar/agenttaint.cedar").read_text())


def test_every_cedar_rule_has_a_unique_id() -> None:
    assert len(CEDAR_IDS) == 20
    assert len(set(CEDAR_IDS)) == len(CEDAR_IDS)


def test_tier_split_ids_exist() -> None:
    for pid in (
        "allow-high-user-authorized-authority",
        "allow-medium-user-authorized-authority",
        "allow-medium",
        "allow-low",
    ):
        assert pid in CEDAR_IDS
    assert "allow-user-authorized-authority" not in CEDAR_IDS
    assert "allow-low-medium" not in CEDAR_IDS


def test_python_adapter_only_emits_ids_defined_in_cedar() -> None:
    source = (POLICY_DIR / "adapter.py").read_text()
    emitted = set(re.findall(r'policy_id=(?:"([^"]+)"|[^,]*?"([^"]+)" if[^,]*?"([^"]+)")', source))
    flat = {x for tup in emitted for x in tup if x}
    flat |= set(re.findall(r'"(allow-[a-z-]+)"', source))
    assert flat, "no policy ids found in adapter.py"
    flat -= {"allow-default", "deny-default"}  # engine-level 'no rule matched' fallbacks
    assert flat <= set(CEDAR_IDS), flat - set(CEDAR_IDS)


def test_every_cedar_id_has_an_engine_explanation() -> None:
    engine = (POLICY_DIR / "cedar_engine.py").read_text()
    for pid in CEDAR_IDS:
        assert f'"{pid}"' in engine, f"missing explanation for {pid}"
