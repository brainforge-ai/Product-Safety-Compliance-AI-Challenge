"""Orchestrates product file evaluation (extract → parse → match → decide)."""

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
from app.domain.models import EvaluationResult, ExtractedProduct, LlmUsage
from app.domain.parsing.csv_product_parser import parse_csv_row
from app.domain.parsing.llm_fallback import LlmFallbackExtractor
from app.domain.parsing.product_parser import parse_product_text
from app.domain.persistence.base import EvaluationRepository

logger = logging.getLogger(__name__)

_EXTRACTORS = {
    FileType.PDF: PdfExtractor(),
    FileType.IMAGE: ImageExtractor(),
    FileType.TEXT: TextExtractor(),
}

DEFAULT_BATCH_CONCURRENCY = 8


def _csv_row_as_text(row: dict[str, str]) -> str:
    """Serialize a CSV row as key: value lines for LLM extraction fallback."""
    return "\n".join(f"{key}: {value}" for key, value in row.items())


@dataclass
class ProductEvaluation:
    """Pairs ExtractedProduct with EvaluationResult for product_id persistence."""

    product: ExtractedProduct
    result: EvaluationResult


async def evaluate_products_from_file(
    path: Path,
    forbidden_list: list[str],
    pipeline: MatchPipeline,
    *,
    llm_matcher: LlmMatcher | None = None,
    extraction_fallback: LlmFallbackExtractor | None = None,
    forbidden_list_version: str = "",
) -> list[ProductEvaluation]:
    """Returns one result per product; multi-row CSVs yield multiple."""
    file_type = await run_in_threadpool(detect_file_type, path)

    if file_type == FileType.CSV:
        rows = await run_in_threadpool(CsvExtractor().extract, path)
        products = [parse_csv_row(row) for row in rows]
        raw_texts = [_csv_row_as_text(row) for row in rows]
    else:
        raw_text = await run_in_threadpool(_EXTRACTORS[file_type].extract, path)
        products = [parse_product_text(raw_text)]
        raw_texts = [raw_text]

    extraction_usages: list[LlmUsage | None] = [None] * len(products)
    if extraction_fallback is not None:
        updated_products: list[ExtractedProduct] = []
        for index, (product, text) in enumerate(zip(products, raw_texts, strict=True)):
            if not product.needs_llm_fallback:
                updated_products.append(product)
                continue
            outcome = await extraction_fallback.extract(text, product)
            updated_products.append(outcome.product)
            extraction_usages[index] = outcome.usage
        products = updated_products

    evaluations = [
        ProductEvaluation(
            product=product,
            result=merge_llm_matches(decide(product, forbidden_list, pipeline), [], usage),
        )
        for product, usage in zip(products, extraction_usages, strict=True)
    ]

    if llm_matcher is None:
        return evaluations

    resolved: list[ProductEvaluation] = []
    for item in evaluations:
        outcome = await llm_matcher.match_unresolved(
            unresolved_ingredients(item.product, item.result),
            forbidden_list,
            forbidden_list_version,
        )
        resolved.append(
            ProductEvaluation(
                product=item.product,
                result=merge_llm_matches(item.result, outcome.matches, outcome.usage),
            )
        )
    return resolved


def persist_evaluation(
    repo: EvaluationRepository,
    item: ProductEvaluation,
    *,
    product_id: str | None = None,
) -> None:
    """Save one evaluation result when persistence is enabled."""
    repo.save_evaluation(item.result, product_id=product_id or item.product.product_id)


async def evaluate_paths_concurrently(
    paths: list[Path],
    forbidden_list: list[str],
    pipeline: MatchPipeline,
    *,
    concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    llm_matcher: LlmMatcher | None = None,
    extraction_fallback: LlmFallbackExtractor | None = None,
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
                    extraction_fallback=extraction_fallback,
                    forbidden_list_version=forbidden_list_version,
                )
            except AppError as exc:
                return exc
            except Exception as exc:  # noqa: BLE001 - isolate unexpected failures too
                logger.warning("Unexpected error evaluating %s: %s", path, exc)
                return exc

    return await asyncio.gather(*[_run(p) for p in paths])
