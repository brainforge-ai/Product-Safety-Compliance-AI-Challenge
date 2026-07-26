"""LLM-based extraction fallback, used when `ExtractedProduct.needs_llm_fallback`
is True (no ingredients section could be found by the regex/heuristic parser).

`LlmExtractionFallback` is the raw port implemented by the concrete Pydantic
AI / Gemini adapter (`infra/llm/pydantic_ai_extraction_fallback.py`).
`LlmFallbackExtractor` wraps it with the same timeout + fail-open guarantee
as tier 6 matching (ARCHITECTURE.md Section 7, `domain/matching/llm_matcher.py`):
a Gemini outage or timeout must never break evaluation, so on any error the
original (unresolved) product is returned unchanged rather than raising.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from app.domain.models import ExtractedProduct, LlmUsage

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0


@dataclass
class LlmExtractionOutcome:
    product: ExtractedProduct
    usage: LlmUsage | None = None


class LlmExtractionFallback(Protocol):
    """Given raw text that the structured parser could not find ingredients
    in, attempt to extract product fields via an LLM.
    """

    async def extract(self, raw_text: str) -> LlmExtractionOutcome: ...


class LlmFallbackExtractor:
    def __init__(
        self,
        client: LlmExtractionFallback,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def extract(self, raw_text: str, fallback: ExtractedProduct) -> LlmExtractionOutcome:
        """Attempt LLM extraction; on any error or timeout, fail open by
        returning `fallback` (the original regex/heuristic-parsed product)
        unchanged, with no usage (no successful call to report cost for).
        """
        try:
            return await asyncio.wait_for(
                self._client.extract(raw_text), timeout=self._timeout_seconds
            )
        except Exception as exc:  # noqa: BLE001 - fail open, an LLM outage must never break evaluation
            logger.warning("LLM extraction fallback failed open: %s", exc)
            return LlmExtractionOutcome(product=fallback, usage=None)
