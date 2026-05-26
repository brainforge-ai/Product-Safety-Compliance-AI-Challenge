"""
Core Pydantic models for the Product Safety Compliance system.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IngredientKind(str, Enum):
    """Classification of ingredient string type."""
    FORMULA = "formula"  # e.g., C6H6, H2O2
    NAME = "name"        # e.g., Benzene, Sodium Benzoate


class MatchLayer(str, Enum):
    """Which matching layer found the hit."""
    A_EXACT = "A_exact"
    A_ALIAS = "A_alias"
    B_PUBCHEM = "B_pubchem"
    C_LLM = "C_llm"


class ProductStatus(str, Enum):
    """Final evaluation status."""
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class MatchHit(BaseModel):
    """A single match between a product ingredient and a forbidden entry."""
    ingredient: str
    forbidden_match: str
    layer: MatchLayer
    confidence: float = 1.0
    cid: Optional[int] = None
    reasoning: Optional[str] = None


class ProductExtraction(BaseModel):
    """Extracted data from a product file."""
    product_id: Optional[str] = None
    product_name: str
    sku: Optional[str] = None
    ingredients: list[str]
    extraction_method: str  # "text", "pdf_vision", "image_vision"
    raw_text: Optional[str] = None


class MatchTrace(BaseModel):
    """Detailed trace of the matching process for debugging/logging."""
    layer_a_checks: int = 0
    layer_a_hits: int = 0
    layer_b_checks: int = 0
    layer_b_hits: int = 0
    layer_b_errors: int = 0
    layer_c_checks: int = 0
    layer_c_hits: int = 0
    pubchem_calls: int = 0
    llm_calls: int = 0


class EvaluationResult(BaseModel):
    """Complete evaluation result for a single product."""
    product_id: Optional[str] = None
    product_name: str
    filename: str
    status: ProductStatus
    reason: list[str] = Field(default_factory=list)
    hits: list[MatchHit] = Field(default_factory=list)
    ingredients_detected: list[str] = Field(default_factory=list)
    trace: MatchTrace = Field(default_factory=MatchTrace)
    extraction_method: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0


class BatchEvaluationResult(BaseModel):
    """Result of batch evaluation."""
    requested: int
    evaluated: int
    skipped: int
    errors: int
    accepted: int
    rejected: int
    results: list[EvaluationResult]
    total_duration_ms: float
