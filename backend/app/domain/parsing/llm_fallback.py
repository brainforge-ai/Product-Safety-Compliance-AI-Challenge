"""LLM extraction fallback when regex parsing finds no ingredients section."""

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
        """Fail open on error or timeout, returning fallback unchanged."""
        try:
            return await asyncio.wait_for(
                self._client.extract(raw_text), timeout=self._timeout_seconds
            )
        except Exception as exc:  # noqa: BLE001 - fail open, an LLM outage must never break evaluation
            logger.warning("LLM extraction fallback failed open: %s", exc)
            return LlmExtractionOutcome(product=fallback, usage=None)
