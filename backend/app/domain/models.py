"""Framework-free domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class MatchMethod(StrEnum):
    EXACT = "exact"
    FORMULA = "formula"
    FUZZY = "fuzzy"
    ACRONYM = "acronym"
    EMBEDDING = "embedding"
    LLM = "llm"


class Ingredient(BaseModel):
    raw_text: str
    normalized_text: str | None = None


class MatchResult(BaseModel):
    forbidden_ingredient: str
    matched_text: str
    method: MatchMethod
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedProduct(BaseModel):
    product_id: str | None = None
    product_name: str
    sku: str | None = None
    description: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    needs_llm_fallback: bool = False


class LlmUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    estimated_cost_usd: float | None = None


class EvaluationResult(BaseModel):
    product_name: str
    status: Literal["Accepted", "Rejected"]
    reason: list[str] = Field(default_factory=list)
    matches: list[MatchResult] = Field(default_factory=list)
    llm_usage: LlmUsage | None = None


class StoredEvaluation(BaseModel):
    id: int | None = None
    product_id: str | None = None
    created_at: datetime
    result: EvaluationResult
