"""
Matching package - 3-layer ingredient safety matching.
"""
from src.core.matching.forbidden import ForbiddenIndex
from src.core.matching.pubchem import PubChemClient
from src.core.matching.pipeline import MatchPipeline
from src.core.matching.normalize import (
    classify,
    to_hill,
    normalize_name,
    is_formula,
)

__all__ = [
    "ForbiddenIndex",
    "PubChemClient",
    "MatchPipeline",
    "classify",
    "to_hill",
    "normalize_name",
    "is_formula",
]
