"""Interface stub for LLM-based extraction fallback.

Used when `ExtractedProduct.needs_llm_fallback` is True (no ingredients
section could be found by the regex/heuristic parser). The concrete
implementation, backed by the Pydantic AI / Gemini adapter described in
docs/ARCHITECTURE.md Section 7, is wired in Phase 8.
"""

from typing import Protocol

from app.domain.models import ExtractedProduct


class LlmExtractionFallback(Protocol):
    """Given raw text that the structured parser could not find ingredients
    in, attempt to extract product fields via an LLM.
    """

    def extract(self, raw_text: str) -> ExtractedProduct: ...


# TODO(Phase 8): implement a concrete LlmExtractionFallback backed by
# infra/llm's Pydantic AI adapter, and wire it into the parsing service so
# that needs_llm_fallback=True results are retried through the LLM instead
# of being treated as having zero ingredients.
