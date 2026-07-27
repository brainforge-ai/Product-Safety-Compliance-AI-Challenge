import asyncio

from app.domain.models import ExtractedProduct, LlmUsage
from app.domain.parsing.llm_fallback import (
    LlmExtractionFallback,
    LlmExtractionOutcome,
    LlmFallbackExtractor,
)

FALLBACK_PRODUCT = ExtractedProduct(product_name="Unknown Product", needs_llm_fallback=True)


class FakeExtractionClient(LlmExtractionFallback):
    def __init__(
        self,
        outcome: LlmExtractionOutcome | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outcome = outcome
        self.error = error
        self.calls: list[str] = []

    async def extract(self, raw_text: str) -> LlmExtractionOutcome:
        self.calls.append(raw_text)
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


class HangingExtractionClient(LlmExtractionFallback):
    async def extract(self, raw_text: str) -> LlmExtractionOutcome:
        await asyncio.sleep(10)
        return LlmExtractionOutcome(product=FALLBACK_PRODUCT)


async def test_successful_extraction_returns_the_llm_result_and_usage() -> None:
    recovered = ExtractedProduct(
        product_name="Synthetic Serum",
        ingredients=["Water", "Glycerin"],
        needs_llm_fallback=False,
    )
    usage = LlmUsage(input_tokens=20, output_tokens=10, total_tokens=30, estimated_cost_usd=0.001)
    client = FakeExtractionClient(outcome=LlmExtractionOutcome(product=recovered, usage=usage))
    extractor = LlmFallbackExtractor(client)

    outcome = await extractor.extract("raw messy text", FALLBACK_PRODUCT)

    assert outcome.product == recovered
    assert outcome.usage == usage
    assert client.calls == ["raw messy text"]


async def test_fails_open_on_client_error_by_returning_the_original_product() -> None:
    client = FakeExtractionClient(error=RuntimeError("Gemini is down"))
    extractor = LlmFallbackExtractor(client)

    outcome = await extractor.extract("raw messy text", FALLBACK_PRODUCT)

    assert outcome.product is FALLBACK_PRODUCT
    assert outcome.usage is None


async def test_fails_open_on_timeout_by_returning_the_original_product() -> None:
    extractor = LlmFallbackExtractor(HangingExtractionClient(), timeout_seconds=0.05)

    outcome = await extractor.extract("raw messy text", FALLBACK_PRODUCT)

    assert outcome.product is FALLBACK_PRODUCT
    assert outcome.usage is None
