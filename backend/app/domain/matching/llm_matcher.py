"""Tier 6 (optional): batched Gemini reasoning match via Pydantic AI
(ARCHITECTURE.md Section 7).

**Deliberate deviation from "register into the MatchPipeline"** (see
docs/IMPLEMENTATION_PLAN.md Phase 8 notes): `Agent.run` is async, while
`MatchPipeline`/`Matcher.match` is synchronous and stateless, and
`app.state.match_pipeline` is a single instance shared across products
evaluated concurrently under `evaluate_paths_concurrently`'s bounded
semaphore. A `Matcher.match(ingredient, forbidden_entry)` call has no
product-level context, so a matcher that tried to batch "all of this
product's unresolved ingredients" by accumulating state between `match()`
calls on a shared singleton would interleave unrelated concurrent products.
Instead, this tier runs once per product, as an async step in
`services/evaluation_service.py`, *after* the tiers 1-5 `MatchPipeline` has
resolved everything it can -- it is never registered as a `Matcher` and
never appears inside `MatchPipeline` itself.

Applies the cache-then-call-then-cache pattern from ARCHITECTURE.md Section
7: every ingredient is checked against `LlmResponseCache` first (keyed by
normalized ingredient + forbidden-list version); only ingredients missing
from the cache are sent to the LLM, in one batched call carrying the whole
unresolved set plus the active forbidden list. Both positive and negative
("no match") outcomes are cached so reruns and repeated evaluations never
re-spend credits. Fails open -- treats every ingredient in the batch as
unmatched and logs a warning -- on any client error or timeout, since an LLM
outage must never take down an evaluation request.

**Formula-shaped ingredients are excluded from the LLM tier entirely**,
mirroring tier 5's exclusion for the same reason: tier 2 already resolves
formula equality exhaustively and precisely via strict, order-independent
parsing, and an LLM asked to "reason" about whether two formulas are the
same substance can hallucinate a confident but wrong answer. **Caught by
manual full-batch verification, not by any unit test:** with tier 6 live
against a real Gemini call, sample P-2025-0022's `C6H8O7` (citric acid) was
matched to forbidden `C8H10N4O2` (caffeine) -- two chemically unrelated
formulas -- at confidence 1.0, flipping the sample from its correct
Accepted status to a false Rejected. Automated per-matcher tests with a
mocked client couldn't have caught this: the mock only ever returns what the
test tells it to. Regression-guarded in
`tests/unit/test_llm_matcher.py::test_formula_shaped_ingredients_are_never_sent_to_the_llm`.
"""

import asyncio
import logging

from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.formula_parser import is_formula
from app.domain.normalization.text_normalizer import normalize_text
from app.infra.cache.llm_response_cache import LlmResponseCache
from app.infra.llm.base import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0


class LlmMatcher:
    def __init__(
        self,
        client: LLMClient,
        cache: LlmResponseCache,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        self._cache = cache
        self._timeout_seconds = timeout_seconds

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    async def match_unresolved(
        self,
        ingredients: list[str],
        forbidden_list: list[str],
        forbidden_list_version: str,
    ) -> list[MatchResult]:
        if not ingredients or not forbidden_list:
            return []

        candidates = [ingredient for ingredient in ingredients if not is_formula(ingredient)]
        if not candidates:
            return []

        results_by_ingredient: dict[str, MatchResult | None] = {}
        to_query: list[str] = []
        for ingredient in candidates:
            hit, cached = self._cache.get(normalize_text(ingredient), forbidden_list_version)
            if hit:
                results_by_ingredient[ingredient] = cached
            else:
                to_query.append(ingredient)

        if to_query:
            results_by_ingredient.update(
                await self._query_and_cache(to_query, forbidden_list, forbidden_list_version)
            )

        return [
            result
            for ingredient in ingredients
            if (result := results_by_ingredient.get(ingredient)) is not None
        ]

    async def _query_and_cache(
        self,
        ingredients: list[str],
        forbidden_list: list[str],
        forbidden_list_version: str,
    ) -> dict[str, MatchResult | None]:
        results: dict[str, MatchResult | None] = dict.fromkeys(ingredients)

        try:
            response = await asyncio.wait_for(
                self._client.match_ingredients(ingredients, forbidden_list),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fail open, an LLM outage must never break evaluation
            logger.warning("LLM matching tier failed open: %s", exc)
            for ingredient in ingredients:
                self._cache.set(normalize_text(ingredient), forbidden_list_version, None)
            return results

        for match in response.matches:
            # Guard against a hallucinated ingredient/forbidden-entry pair
            # that wasn't actually part of the request.
            if (
                match.ingredient not in ingredients
                or match.forbidden_ingredient not in forbidden_list
            ):
                continue
            results[match.ingredient] = MatchResult(
                forbidden_ingredient=match.forbidden_ingredient,
                matched_text=match.ingredient,
                method=MatchMethod.LLM,
                confidence=match.confidence,
            )

        for ingredient in ingredients:
            self._cache.set(normalize_text(ingredient), forbidden_list_version, results[ingredient])

        return results
