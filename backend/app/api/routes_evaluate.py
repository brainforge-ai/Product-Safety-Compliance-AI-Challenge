"""Evaluation endpoints."""

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
    get_llm_extraction_fallback,
    get_llm_matcher,
    get_match_pipeline,
    get_settings_dep,
)
from app.api.schemas.evaluate import BatchEvaluationResponse, BatchItemResult, EvaluateByPathRequest
from app.core.config import Settings
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult
from app.domain.parsing.llm_fallback import LlmFallbackExtractor
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
    """Reject path traversal for by-path and batch-samples requests."""
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
                "/evaluate/by-path only supports a single product."
            ),
        )
    return items[0]


@router.post("/evaluate", response_model=EvaluationResult | BatchEvaluationResponse)
async def evaluate(
    files: list[UploadFile],
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
    llm_matcher: LlmMatcher | None = Depends(get_llm_matcher),
    extraction_fallback: LlmFallbackExtractor | None = Depends(get_llm_extraction_fallback),
) -> EvaluationResult | BatchEvaluationResponse:
    """Returns single EvaluationResult or batch shape depending on product count."""
    forbidden_list = forbidden_repo.get_all()
    forbidden_list_version = forbidden_repo.version_hash()

    with ExitStack() as stack:
        staged: list[tuple[str, Path]] = []
        for upload in files:
            path = stack.enter_context(_staged_upload(upload))
            await _write_upload(upload, path)
            staged.append((upload.filename or "uploaded file", path))

        if len(staged) == 1:
            filename, path = staged[0]
            items = await evaluate_products_from_file(
                path,
                forbidden_list,
                pipeline,
                llm_matcher=llm_matcher,
                extraction_fallback=extraction_fallback,
                forbidden_list_version=forbidden_list_version,
            )
            if len(items) == 1:
                persist_evaluation(evaluation_repo, items[0])
                return items[0].result
            return BatchEvaluationResponse(
                results=_to_batch_items(filename, items, evaluation_repo)
            )

        outcomes = await evaluate_paths_concurrently(
            [path for _, path in staged],
            forbidden_list,
            pipeline,
            llm_matcher=llm_matcher,
            extraction_fallback=extraction_fallback,
            forbidden_list_version=forbidden_list_version,
        )

        results = [
            _to_batch_items(filename, outcome, evaluation_repo)
            for (filename, _), outcome in zip(staged, outcomes, strict=True)
        ]

    return BatchEvaluationResponse(results=[item for group in results for item in group])


@router.post("/evaluate/by-path", response_model=EvaluationResult)
async def evaluate_by_path(
    body: EvaluateByPathRequest,
    settings: Settings = Depends(get_settings_dep),
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
    llm_matcher: LlmMatcher | None = Depends(get_llm_matcher),
    extraction_fallback: LlmFallbackExtractor | None = Depends(get_llm_extraction_fallback),
) -> EvaluationResult:
    resolved = _resolve_within(settings.sample_data_dir, body.path)
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"No such file: {body.path}")

    items = await evaluate_products_from_file(
        resolved,
        forbidden_repo.get_all(),
        pipeline,
        llm_matcher=llm_matcher,
        extraction_fallback=extraction_fallback,
        forbidden_list_version=forbidden_repo.version_hash(),
    )

    item = _single_result(items, source=body.path)
    persist_evaluation(evaluation_repo, item)
    return item.result


@router.post("/evaluate/batch-samples", response_model=BatchEvaluationResponse)
async def evaluate_batch_samples(
    settings: Settings = Depends(get_settings_dep),
    forbidden_repo: ForbiddenListRepository = Depends(get_forbidden_list_repository),
    pipeline: MatchPipeline = Depends(get_match_pipeline),
    evaluation_repo: EvaluationRepository = Depends(get_evaluation_repository),
    llm_matcher: LlmMatcher | None = Depends(get_llm_matcher),
    extraction_fallback: LlmFallbackExtractor | None = Depends(get_llm_extraction_fallback),
) -> BatchEvaluationResponse:
    index_path = settings.sample_data_dir / "product_index.csv"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail=f"No product_index.csv found at {index_path}")

    with index_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    forbidden_list = forbidden_repo.get_all()
    paths = [settings.sample_data_dir / row["filename"] for row in rows]
    outcomes = await evaluate_paths_concurrently(
        paths,
        forbidden_list,
        pipeline,
        llm_matcher=llm_matcher,
        extraction_fallback=extraction_fallback,
        forbidden_list_version=forbidden_repo.version_hash(),
    )

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
