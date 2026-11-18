"""Milestone 6: benchmark loader, metrics, and smoke evaluation."""

from __future__ import annotations

from pathlib import Path

from agenttaint_benchmark.defenses import DefenseConfig, default_defense_matrix
from agenttaint_benchmark.loader import dataset_version, load_scenarios
from agenttaint_benchmark.metrics import aggregate
from agenttaint_benchmark.runner import run_scenario
from agenttaint_benchmark.schema import AblationModeName, DefenseMode, Split

ROOT = Path(__file__).resolve().parents[2]


def test_dataset_version_and_splits() -> None:
    version = dataset_version()
    assert version.startswith("2026.")
    for split in (Split.TRAIN, Split.DEV, Split.TEST):
        ver, scenarios = load_scenarios(split)
        assert ver == version
        assert scenarios
        assert all(s.split == split for s in scenarios)


def test_held_out_test_avoids_unit_fixture_recipients() -> None:
    _, scenarios = load_scenarios(Split.TEST)
    banned = {"attacker@example.com", "bob@corp.example", "evil@exfil.test"}
    for sc in scenarios:
        if sc.send_to:
            assert sc.send_to.casefold() not in banned
    assert len(scenarios) >= 60
    assert any(sc.difficulty == "hard" for sc in scenarios)
    families = {sc.family.value for sc in scenarios}
    for required in {
        "heavy_paraphrase",
        "multi_hop",
        "memory_poison",
        "forged_metadata",
        "ambiguous",
    }:
        assert required in families


def test_argument_parent_modes_forged_metadata() -> None:
    from agenttaint_benchmark.defenses import DefenseConfig
    from agenttaint_benchmark.schema import AblationModeName, DefenseMode

    _, scenarios = load_scenarios(Split.TEST)
    forged = next(s for s in scenarios if s.scenario_id.startswith("test-atk-forged-01"))
    assert forged.argument_parent_mode == "user"
    # Reconstruction should still stop auto-exfil even if parents claim USER.
    row = run_scenario(
        forged,
        DefenseConfig(DefenseMode.RECONSTRUCTION_ONLY, AblationModeName.COMBINED),
    )
    assert row.attack_success is False


def test_metrics_asr_utility() -> None:
    from agenttaint_benchmark.schema import ScenarioRunResult

    rows = [
        ScenarioRunResult(
            scenario_id="a1",
            split="test",
            kind="attack",
            family="direct",
            defense="combined",
            ablation="combined",
            decision="BLOCK",
            attack_success=False,
            latency_ms=1.0,
        ),
        ScenarioRunResult(
            scenario_id="a2",
            split="test",
            kind="attack",
            family="direct",
            defense="combined",
            ablation="combined",
            decision="ALLOW",
            attack_success=True,
            latency_ms=2.0,
        ),
        ScenarioRunResult(
            scenario_id="b1",
            split="test",
            kind="benign",
            family="benign_authorized",
            defense="combined",
            ablation="combined",
            decision="ALLOW",
            benign_completed=True,
            latency_ms=1.5,
        ),
    ]
    m = aggregate(rows)
    assert m.n_attack == 2
    assert m.asr == 0.5
    assert m.utility == 1.0


def test_runner_smoke_undefended_and_combined() -> None:
    _, scenarios = load_scenarios(Split.TEST)
    attack = next(s for s in scenarios if s.scenario_id == "test-atk-direct-01")
    benign = next(s for s in scenarios if s.scenario_id == "test-ben-auth-01")

    undef = run_scenario(attack, DefenseConfig(DefenseMode.UNDEFENDED))
    assert undef.decision == "ALLOW"
    assert undef.attack_success is True

    combined = run_scenario(attack, DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED))
    assert combined.decision in {"BLOCK", "CONFIRM"}
    assert combined.attack_success is False
    assert all(s != "KNOWN" for s in combined.evidence_statuses)

    ok = run_scenario(benign, DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED))
    assert ok.decision == "ALLOW"
    assert ok.benign_completed is True


def test_default_defense_matrix_covers_required_baselines() -> None:
    modes = {d.mode for d in default_defense_matrix()}
    assert modes == {
        DefenseMode.UNDEFENDED,
        DefenseMode.COARSE_TAINT,
        DefenseMode.EXPLICIT_ONLY,
        DefenseMode.RECONSTRUCTION_ONLY,
        DefenseMode.COMBINED,
    }
