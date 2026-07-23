"""Evaluation endpoints (ARCHITECTURE.md Section 10)."""

import csv
import os
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.deps import (
    get_evaluation_repository,
    get_forbidden_list_repository,
    get_match_pipeline,
    get_settings_dep,
)
from app.api.schemas.evaluate import BatchEvaluationResponse, BatchItemResult, EvaluateByPathRequest
from app.core.config import Settings
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult
from app.domain.persistence.base import EvaluationRepository
from app.services.evaluation_service import (
    ProductEvaluation,
    evaluate_paths_concurrently,
    evaluate_products_from_file,
    persist_evaluation,
)

router = APIRouter()


@contextmanager
def _staged_upload(upload: UploadFile) -> Iterator[Path]:
    suffix = Path(upload.filename or "").suffix
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    path = Path(name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


async def _write_upload(upload: UploadFile, path: Path) -> None:
    content = await upload.read()
    await run_in_threadpool(path.write_bytes, content)


def _resolve_within(base: Path, relative: str) -> Path:
    """Resolve `relative` under `base`, rejecting any attempt to escape it
    (e.g. `../../etc/passwd`) — `by-path`/`batch-samples` accept a path
    string from the request, so this is the boundary against path traversal.
    """
    candidate = (base / relative).resolve()
    base_resolved = base.resolve()
    if not (candidate == base_resolved or base_resolved in candidate.parents):
        raise HTTPException(
            status_code=400, detail=f"Path escapes sample data directory: {relative}"
        )
    return candidate


def _single_result(
    items: list[ProductEvaluation], *, source: str
) -> ProductEvaluation:
    if len(items) != 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{source} contains {len(items)} product rows; "
                "/evaluate only supports a single product. Use /evaluate/batch for multi-row CSVs."
            ),
        )
    return items[0]


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate(
    file: UploadFile,
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationResult:
    with _staged_upload(file) as path:
        await _write_upload(file, path)
        items = await evaluate_products_from_file(path, forbidden_repo.get_all(), pipeline)

    item = _single_result(items, source=file.filename or "uploaded file")
    persist_evaluation(evaluation_repo, item)
    return item.result


@router.post("/evaluate/batch", response_model=BatchEvaluationResponse)
async def evaluate_batch(
    files: list[UploadFile],
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
) -> BatchEvaluationResponse:
    forbidden_list = forbidden_repo.get_all()

    with ExitStack() as stack:
        staged_paths = []
        for upload in files:
            path = stack.enter_context(_staged_upload(upload))
            await _write_upload(upload, path)
            staged_paths.append(path)

        outcomes = await evaluate_paths_concurrently(staged_paths, forbidden_list, pipeline)

        results = [
            _to_batch_items(upload.filename or "uploaded file", outcome, evaluation_repo)
            for upload, outcome in zip(files, outcomes, strict=True)
        ]

    return BatchEvaluationResponse(results=[item for group in results for item in group])


@router.post("/evaluate/by-path", response_model=EvaluationResult)
async def evaluate_by_path(
    body: EvaluateByPathRequest,
    settings: Settings = Depends(get_settings_dep),
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
) -> EvaluationResult:
    resolved = _resolve_within(settings.sample_data_dir, body.path)
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"No such file: {body.path}")

    items = await evaluate_products_from_file(resolved, forbidden_repo.get_all(), pipeline)

    item = _single_result(items, source=body.path)
    persist_evaluation(evaluation_repo, item)
    return item.result


@router.post("/evaluate/batch-samples", response_model=BatchEvaluationResponse)
async def evaluate_batch_samples(
    settings: Settings = Depends(get_settings_dep),
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
) -> BatchEvaluationResponse:
    index_path = settings.sample_data_dir / "product_index.csv"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail=f"No product_index.csv found at {index_path}")

    with index_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    forbidden_list = forbidden_repo.get_all()
    paths = [settings.sample_data_dir / row["filename"] for row in rows]
    outcomes = await evaluate_paths_concurrently(paths, forbidden_list, pipeline)

    results = [
        _to_batch_items(row["filename"], outcome, evaluation_repo, product_id=row.get("product_id"))
        for row, outcome in zip(rows, outcomes, strict=True)
    ]

    return BatchEvaluationResponse(results=[item for group in results for item in group])


def _to_batch_items(
    filename: str,
    outcome: list[ProductEvaluation] | Exception,
    evaluation_repo: EvaluationRepository,
    *,
    product_id: str | None = None,
) -> list[BatchItemResult]:
    if isinstance(outcome, Exception):
        return [
            BatchItemResult(
                filename=filename,
                product_id=product_id,
                status="error",
                error=str(outcome),
            )
        ]

    items = []
    for item in outcome:
        resolved_product_id = product_id or item.product.product_id
        persist_evaluation(evaluation_repo, item, product_id=resolved_product_id)
        items.append(
            BatchItemResult(
                filename=filename,
                product_id=resolved_product_id,
                status="ok",
                result=item.result,
            )
        )
    return items
