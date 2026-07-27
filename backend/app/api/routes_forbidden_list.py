"""Forbidden ingredient list endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import get_evaluation_repository, get_forbidden_list_repository
from app.api.schemas.forbidden_list import ForbiddenListResponse
from app.core.exceptions import ParsingError
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.persistence.base import EvaluationRepository
from app.services.forbidden_list_service import replace_forbidden_list_from_upload

router = APIRouter()


@router.get("/forbidden-ingredients", response_model=ForbiddenListResponse)
async def get_forbidden_ingredients(
    repository: ForbiddenListRepository = Depends(get_forbidden_list_repository),
) -> ForbiddenListResponse:
    """Return the current forbidden ingredient list."""
    return ForbiddenListResponse(ingredients=repository.get_all())


@router.post("/forbidden-ingredients", response_model=ForbiddenListResponse)
async def replace_forbidden_ingredients(
    file: UploadFile,
    repository: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    evaluation_repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> ForbiddenListResponse:
    """Replace the forbidden list from an uploaded CSV file."""
    try:
        entries = await replace_forbidden_list_from_upload(file, repository, evaluation_repository)
    except ParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ForbiddenListResponse(ingredients=entries)
