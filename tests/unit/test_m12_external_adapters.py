"""M12: external adapters must refuse fabricated scores."""

from __future__ import annotations

import pytest
from agenttaint_benchmark.external_adapters import (
    ExternalBenchmarkNotEvaluated,
    probe_agentdojo,
    probe_injecagent,
    run_agentdojo_adapter,
    run_injecagent_adapter,
)


def test_agentdojo_probe_free_local_asr_impossible() -> None:
    f = probe_agentdojo()
    assert f.free_local_asr_possible is False
    assert f.blockers


def test_injecagent_probe_free_local_asr_impossible() -> None:
    f = probe_injecagent()
    assert f.free_local_asr_possible is False
    assert f.blockers


def test_adapters_refuse_evaluation() -> None:
    with pytest.raises(ExternalBenchmarkNotEvaluated, match="not evaluated"):
        run_agentdojo_adapter()
    with pytest.raises(ExternalBenchmarkNotEvaluated, match="not evaluated"):
        run_injecagent_adapter()
