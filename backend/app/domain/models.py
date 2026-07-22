"""Framework-free domain models shared across extraction, matching, and the API layer.

These models must not import anything from FastAPI, SQLModel, or the LLM
client, per the ports-and-adapters principle in docs/ARCHITECTURE.md
(Section 3).
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class MatchMethod(StrEnum):
    """Which matching tier produced a given match, per ARCHITECTURE.md Section 6."""

    EXACT = "exact"
    FORMULA = "formula"
    FUZZY = "fuzzy"
    ACRONYM = "acronym"
    EMBEDDING = "embedding"
    LLM = "llm"


class Ingredient(BaseModel):
    """A single ingredient as extracted from a product file, before or after normalization."""

    raw_text: str
    normalized_text: str | None = None


class MatchResult(BaseModel):
    """A confident match between a product ingredient and a forbidden ingredient entry."""

    forbidden_ingredient: str
    matched_text: str
    method: MatchMethod
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedProduct(BaseModel):
    """The structured fields pulled out of a raw product file by the parsing layer."""

    product_id: str | None = None
    product_name: str
    sku: str | None = None
    description: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    needs_llm_fallback: bool = False


class EvaluationResult(BaseModel):
    """The final Accept/Reject decision for a product, matching the challenge README's
    response contract (product_name, status, reason), with an additive `matches` field
    for transparency (ARCHITECTURE.md Section 10).
    """

    product_name: str
    status: Literal["Accepted", "Rejected"]
    reason: list[str] = Field(default_factory=list)
    matches: list[MatchResult] = Field(default_factory=list)


class StoredEvaluation(BaseModel):
    """An `EvaluationResult` as persisted by an `EvaluationRepository`, with the
    record metadata (id, timestamp) added by the persistence layer itself.
    """

    id: int | None = None
    product_id: str | None = None
    created_at: datetime
    result: EvaluationResult
