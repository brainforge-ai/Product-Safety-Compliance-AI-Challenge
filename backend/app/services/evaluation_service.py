"""Orchestrates extraction, parsing, matching, and decisioning for one or more
product files, plus optional persistence of the results.

This module is the "services" layer from ARCHITECTURE.md Section 9: unlike
`domain/`, it is allowed to depend on FastAPI (`run_in_threadpool`, to keep
blocking extraction/OCR work off the event loop per Section 12) and on the
persistence port. Route handlers stay thin and call into here.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from app.core.exceptions import AppError
from app.domain.decision.engine import decide, merge_llm_matches, unresolved_ingredients
from app.domain.extraction.csv_extractor import CsvExtractor
from app.domain.extraction.detector import FileType, detect_file_type
from app.domain.extraction.image_extractor import ImageExtractor
from app.domain.extraction.pdf_extractor import PdfExtractor
from app.domain.extraction.text_extractor import TextExtractor
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult, ExtractedProduct
from app.domain.parsing.csv_product_parser import parse_csv_row
from app.domain.parsing.product_parser import parse_product_text
from app.domain.persistence.base import EvaluationRepository

logger = logging.getLogger(__name__)

_EXTRACTORS = {
    FileType.PDF: PdfExtractor(),
    FileType.IMAGE: ImageExtractor(),
    FileType.TEXT: TextExtractor(),
}

DEFAULT_BATCH_CONCURRENCY = 8


@dataclass
class ProductEvaluation:
    """One product's parsed fields alongside its Accept/Reject decision.

    `ExtractedProduct` is kept around (not just the `EvaluationResult`) so
    callers can persist by `product_id`, which isn't part of the
    README-shaped result itself.
    """

    product: ExtractedProduct
    result: EvaluationResult


async def evaluate_products_from_file(
    path: Path,
    forbidden_list: list[str],
    pipeline: MatchPipeline,
    *,
    llm_matcher: LlmMatcher | None = None,
    forbidden_list_version: str = "",
) -> list[ProductEvaluation]:
    """Evaluate every product found in one file.

    Almost always a single-item list (pdf/image/text files each describe one
    product). A CSV file is the exception: `CsvExtractor` yields one row per
    product, so a multi-row CSV legitimately produces multiple results — the
    `/evaluate` route (which returns a single README-shaped object) rejects
    that case and points callers at `/evaluate/batch` instead.

    When `llm_matcher` is provided (tier 6 is enabled), every product's
    still-unresolved ingredients after tiers 1-5 are batched into one LLM
    call per product and folded into the final result — see
    `domain/matching/llm_matcher.py` for why this happens here rather than
    inside `pipeline`/`decide`.
    """
    file_type = await run_in_threadpool(detect_file_type, path)

    if file_type == FileType.CSV:
        rows = await run_in_threadpool(CsvExtractor().extract, path)
        products = [parse_csv_row(row) for row in rows]
    else:
        raw_text = await run_in_threadpool(_EXTRACTORS[file_type].extract, path)
        products = [parse_product_text(raw_text)]

    evaluations = [
        ProductEvaluation(product=product, result=decide(product, forbidden_list, pipeline))
        for product in products
    ]

    if llm_matcher is None:
        return evaluations

    resolved: list[ProductEvaluation] = []
    for item in evaluations:
        llm_matches = await llm_matcher.match_unresolved(
            unresolved_ingredients(item.product, item.result),
            forbidden_list,
            forbidden_list_version,
        )
        resolved.append(
            ProductEvaluation(
                product=item.product,
                result=merge_llm_matches(item.result, llm_matches),
            )
        )
    return resolved


def persist_evaluation(
    repo: EvaluationRepository,
    item: ProductEvaluation,
    *,
    product_id: str | None = None,
) -> None:
    repo.save_evaluation(item.result, product_id=product_id or item.product.product_id)


async def evaluate_paths_concurrently(
    paths: list[Path],
    forbidden_list: list[str],
    pipeline: MatchPipeline,
    *,
    concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    llm_matcher: LlmMatcher | None = None,
    forbidden_list_version: str = "",
) -> list[list[ProductEvaluation] | Exception]:
    """Evaluate many files concurrently, bounded by a semaphore.

    Each path's outcome is either its list of `ProductEvaluation`s or the
    `Exception` it raised — never a raised exception that would abort the
    rest of the batch. Callers isolate per-file failures from this list.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(path: Path) -> list[ProductEvaluation] | Exception:
        async with semaphore:
            try:
                return await evaluate_products_from_file(
                    path,
                    forbidden_list,
                    pipeline,
                    llm_matcher=llm_matcher,
                    forbidden_list_version=forbidden_list_version,
                )
            except AppError as exc:
                return exc
            except Exception as exc:  # noqa: BLE001 - isolate unexpected failures too
                logger.warning("Unexpected error evaluating %s: %s", path, exc)
                return exc

    return await asyncio.gather(*[_run(p) for p in paths])
