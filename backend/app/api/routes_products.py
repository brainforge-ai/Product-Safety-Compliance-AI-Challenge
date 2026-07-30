"""Evaluation history endpoint."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_evaluation_repository
from app.api.schemas.products import EvaluationHistoryResponse
from app.domain.persistence.base import EvaluationRepository

router = APIRouter()


@router.get("/products", response_model=EvaluationHistoryResponse)
async def list_products(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationHistoryResponse:
    """List persisted evaluation history with pagination."""
    items = repository.list_evaluations(limit=limit, offset=offset)
    return EvaluationHistoryResponse(items=items, limit=limit, offset=offset)
