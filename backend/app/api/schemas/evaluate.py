"""Request/response schemas for /evaluate endpoints."""

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
