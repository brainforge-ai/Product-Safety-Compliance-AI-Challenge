"""Evaluation history endpoint (ARCHITECTURE.md Section 10).

Only populated when `ENABLE_PERSISTENCE=true`; with persistence off,
`NoopEvaluationRepository.list_evaluations()` always returns an empty list.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_evaluation_repository
from app.api.schemas.products import EvaluationHistoryResponse
from app.domain.persistence.base import EvaluationRepository

router = APIRouter()


@router.get("/products", response_model=EvaluationHistoryResponse)
async def list_products(
    limit: int = 50,
    offset: int = 0,
    repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationHistoryResponse:
    items = repository.list_evaluations(limit=limit, offset=offset)
    return EvaluationHistoryResponse(items=items, limit=limit, offset=offset)
