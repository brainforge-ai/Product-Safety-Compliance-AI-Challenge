"""Request/response schemas for the /evaluate endpoints.

`EvaluationResult` itself (the single-product response shape) is reused
directly from `domain/models.py` since it already matches the challenge
README's contract plus the additive `matches` field (ARCHITECTURE.md Section
10); no separate API-layer duplicate is needed for it.
"""

from typing import Literal

from pydantic import BaseModel

from app.domain.models import EvaluationResult


class EvaluateByPathRequest(BaseModel):
    path: str


class BatchItemResult(BaseModel):
    filename: str
    product_id: str | None = None
    status: Literal["ok", "error"]
    result: EvaluationResult | None = None
    error: str | None = None


class BatchEvaluationResponse(BaseModel):
    results: list[BatchItemResult]
