"""Provenance reconstruction: lexical, structural, optional semantic evidence.

All reconstructed links are INFERRED. Similarity scores are evidence signals,
not probabilities of causation.
"""

from agenttaint_reconstruction.engine import (
    AblationMode,
    CandidateRecord,
    ReconstructionEngine,
    ReconstructionResult,
)
from agenttaint_reconstruction.lexical import lexical_similarity
from agenttaint_reconstruction.structural import (
    StructuralHit,
    extract_structural_values,
    normalize_email,
    normalize_url,
    structural_matches,
)

__all__ = [
    "AblationMode",
    "CandidateRecord",
    "ReconstructionEngine",
    "ReconstructionResult",
    "StructuralHit",
    "extract_structural_values",
    "lexical_similarity",
    "normalize_email",
    "normalize_url",
    "structural_matches",
]

__version__ = "0.1.0"
