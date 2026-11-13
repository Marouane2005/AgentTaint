"""Benchmark scenario and result schemas.

Splits:
- train/dev: available during system development (thresholds, policy design)
- test: held-out; must not be used to tune reconstruction thresholds or policies
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Split(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    CHALLENGE = "challenge"


class ScenarioKind(StrEnum):
    ATTACK = "attack"
    BENIGN = "benign"


class ScenarioFamily(StrEnum):
    DIRECT = "direct"
    SUMMARIZED = "summarized"
    PARAPHRASED = "paraphrased"
    EXTRACTED = "extracted"
    MEMORY = "memory"
    MULTI_AGENT = "multi_agent"
    MULTI_SOURCE = "multi_source"
    CONFLICTING = "conflicting"
    MISSING_LINEAGE = "missing_lineage"
    ADAPTIVE_SPLIT = "adaptive_split"
    OBFUSCATED = "obfuscated"
    BENIGN_AUTHORIZED = "benign_authorized"
    BENIGN_OVERLAP = "benign_overlap"
    BENIGN_SIMILAR = "benign_similar"
    BENIGN_LOW_RISK = "benign_low_risk"
    # Milestone 7 expansions
    HEAVY_PARAPHRASE = "heavy_paraphrase"
    MULTI_HOP = "multi_hop"
    MEMORY_POISON = "memory_poison"
    FORGED_METADATA = "forged_metadata"
    AMBIGUOUS = "ambiguous"


class PipelineOp(StrEnum):
    READ_UNTRUSTED = "read_untrusted"
    USER_INSTRUCTION = "user_instruction"
    SUMMARIZE = "summarize"
    PARAPHRASE = "paraphrase"
    EXTRACT = "extract"
    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    DELEGATE = "delegate"
    GAP = "gap"
    SEND = "send"
    READ_ONLY = "read_only"


class PipelineStep(BaseModel):
    op: PipelineOp
    text: str | None = None
    agent_id: str = "agent_a"
    recipient_agent: str | None = None
    memory_key: str | None = None


class Scenario(BaseModel):
    scenario_id: str
    split: Split
    kind: ScenarioKind
    family: ScenarioFamily
    description: str
    pipeline: list[PipelineStep]
    # Final sink arguments (for SEND) or empty for READ_ONLY
    send_to: str | None = None
    send_subject: str = "benchmark"
    send_body: str = "benchmark body"
    # Gold labels
    attack_should_succeed_undefended: bool = True
    gold_untrusted_influences_recipient: bool = False
    gold_user_authorizes_recipient: bool = False
    # Extra USER-authorized values injected into gateway (simulating prior USER spans)
    user_authorized_values: list[str] = Field(default_factory=list)
    # Explicit parent wiring for the sink authority arg:
    # last | user | none | fabricated
    argument_parent_mode: str = "last"
    difficulty: str = "standard"  # standard | hard
    notes: str = ""


class DefenseMode(StrEnum):
    UNDEFENDED = "undefended"
    COARSE_TAINT = "coarse_taint"
    EXPLICIT_ONLY = "explicit_only"
    RECONSTRUCTION_ONLY = "reconstruction_only"
    COMBINED = "combined"


class AblationModeName(StrEnum):
    NONE = "none"
    LEXICAL = "lexical"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    LEXICAL_STRUCTURAL = "lexical_structural"
    COMBINED = "combined"
    EXPLICIT = "explicit"


class ScenarioRunResult(BaseModel):
    scenario_id: str
    split: str
    kind: str
    family: str
    defense: str
    ablation: str
    decision: str
    policy_id: str | None = None
    attack_success: bool | None = None
    benign_completed: bool | None = None
    confirmed: bool = False
    latency_ms: float
    predicted_source_ids: list[str] = Field(default_factory=list)
    gold_source_ids: list[str] = Field(default_factory=list)
    provenance_tp: int = 0
    provenance_fp: int = 0
    provenance_fn: int = 0
    evidence_statuses: list[str] = Field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AggregateMetrics(BaseModel):
    n_scenarios: int
    n_attack: int
    n_benign: int
    asr: float | None = None
    fnr: float | None = None
    fpr_block: float | None = None
    fpr_confirm: float | None = None
    utility: float | None = None
    confirm_rate_attack: float | None = None
    confirm_rate_benign: float | None = None
    provenance_precision: float | None = None
    provenance_recall: float | None = None
    provenance_f1: float | None = None
    latency_ms_median: float | None = None
    latency_ms_p95: float | None = None
    rss_kb_max: float | None = None
    cpu_user_s: float | None = None


class SeedAggregate(BaseModel):
    seed: int
    per_defense: dict[str, AggregateMetrics] = Field(default_factory=dict)


class VariabilitySummary(BaseModel):
    metric: str
    defense: str
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    n_seeds: int = 0


class BenchmarkReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dataset_version: str
    seed: int
    split: str
    defenses: list[str]
    ablations: list[str]
    command: str
    config: dict[str, Any] = Field(default_factory=dict)
    per_defense: dict[str, AggregateMetrics] = Field(default_factory=dict)
    per_ablation: dict[str, AggregateMetrics] = Field(default_factory=dict)
    per_family_combined: dict[str, AggregateMetrics] = Field(default_factory=dict)
    per_difficulty_combined: dict[str, AggregateMetrics] = Field(default_factory=dict)
    challenge_results: list[ScenarioRunResult] = Field(default_factory=list)
    seed_runs: list[SeedAggregate] = Field(default_factory=list)
    variability: list[VariabilitySummary] = Field(default_factory=list)
    results: list[ScenarioRunResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
