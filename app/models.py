"""Pydantic models for API request/response validation."""

from pydantic import BaseModel
from typing import List, Optional


class ForbiddenMatch(BaseModel):
    """Detail about a single forbidden ingredient match."""
    ingredient: str
    matched_forbidden: str
    match_tier: str
    explanation: str


class EvaluationResponse(BaseModel):
    """API response for a product evaluation.

    Core fields (per spec):
        product_name, status, reason

    Additional fields provide transparency for debugging and review.
    """
    product_id: Optional[str] = None
    product_name: str
    source_file: str = ""
    status: str                          # "Accepted", "Rejected", "Needs Review", "Error"
    reason: List[str]
    raw_extracted_text: str = ""
    ingredients_found: List[str] = []
    forbidden_matches: List[ForbiddenMatch] = []
