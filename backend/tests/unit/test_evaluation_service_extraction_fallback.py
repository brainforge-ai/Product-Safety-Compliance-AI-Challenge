"""Unit tests for the extraction-fallback wiring in
`evaluate_products_from_file`: a product the regex/heuristic parser flagged
`needs_llm_fallback=True` should be retried through the LLM fallback before
matching runs, for both a text-blob file and a CSV row, and any token
usage/cost it reports should end up on the final `EvaluationResult`.
"""

from pathlib import Path

import pytest

from app.core.exceptions import ParsingError
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import ExtractedProduct, LlmUsage
from app.domain.parsing.llm_fallback import (
    LlmExtractionFallback,
    LlmExtractionOutcome,
    LlmFallbackExtractor,
)
from app.services.evaluation_service import evaluate_products_from_file

PIPELINE = MatchPipeline([ExactMatcher()])


class FakeExtractionClient(LlmExtractionFallback):
    def __init__(self, outcome: LlmExtractionOutcome) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    async def extract(self, raw_text: str) -> LlmExtractionOutcome:
        self.calls.append(raw_text)
        return self.outcome


async def test_text_file_with_no_ingredients_section_is_retried_through_the_fallback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "product.txt"
    path.write_text("Product Name: Mystery Serum\nDescription:\nNo ingredients section here.\n")

    recovered = ExtractedProduct(
        product_name="Mystery Serum",
        ingredients=["Water", "Coumarin"],
        needs_llm_fallback=False,
    )
    usage = LlmUsage(input_tokens=15, output_tokens=8, total_tokens=23, estimated_cost_usd=0.0005)
    client = FakeExtractionClient(LlmExtractionOutcome(product=recovered, usage=usage))
    extractor = LlmFallbackExtractor(client)

    [evaluation] = await evaluate_products_from_file(
        path, ["Coumarin"], PIPELINE, extraction_fallback=extractor
    )

    assert client.calls  # the raw text blob was actually sent to the LLM
    assert evaluation.product.ingredients == ["Water", "Coumarin"]
    assert evaluation.result.status == "Rejected"
    assert evaluation.result.reason == ["Contains Coumarin"]
    assert evaluation.result.llm_usage == usage


async def test_csv_row_missing_ingredients_column_is_retried_through_the_fallback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "product.csv"
    path.write_text("Product Name\nNo Ingredients Product\n")

    recovered = ExtractedProduct(
        product_name="No Ingredients Product",
        ingredients=["Water"],
        needs_llm_fallback=False,
    )
    client = FakeExtractionClient(LlmExtractionOutcome(product=recovered))
    extractor = LlmFallbackExtractor(client)

    [evaluation] = await evaluate_products_from_file(
        path, ["Coumarin"], PIPELINE, extraction_fallback=extractor
    )

    assert client.calls == ["Product Name: No Ingredients Product"]
    assert evaluation.product.ingredients == ["Water"]
    assert evaluation.result.status == "Accepted"


async def test_product_that_did_not_need_fallback_is_never_sent_to_the_llm(
    tmp_path: Path,
) -> None:
    path = tmp_path / "product.txt"
    path.write_text("Product Name: Clean Serum\nIngredients / Chemical Formulas:\n- Water\n")

    client = FakeExtractionClient(
        LlmExtractionOutcome(product=ExtractedProduct(product_name="should never be used"))
    )
    extractor = LlmFallbackExtractor(client)

    [evaluation] = await evaluate_products_from_file(
        path, ["Coumarin"], PIPELINE, extraction_fallback=extractor
    )

    assert client.calls == []
    assert evaluation.product.product_name == "Clean Serum"
    assert evaluation.result.llm_usage is None


async def test_fallback_failure_raises_instead_of_false_accepting(
    tmp_path: Path,
) -> None:
    path = tmp_path / "product.txt"
    path.write_text("Product Name: Mystery Serum\nDescription:\nNo ingredients section here.\n")

    class ErroringClient:
        async def extract(self, raw_text: str) -> LlmExtractionOutcome:
            raise RuntimeError("Gemini is down")

    extractor = LlmFallbackExtractor(ErroringClient())

    with pytest.raises(ParsingError, match="Could not extract an ingredient list"):
        await evaluate_products_from_file(
            path, ["Coumarin"], PIPELINE, extraction_fallback=extractor
        )
