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

`match_unresolved` returns an `LlmMatchOutcome` carrying token usage/cost for
the single batched call actually made (`None` if every ingredient was served
from cache, or nothing needed querying) -- surfaced end-to-end on
`EvaluationResult.llm_usage` so callers can see what a given evaluation
actually cost.

**Formula-shaped strings are excluded from the LLM tier entirely, on both
sides of the comparison** -- a formula-shaped ingredient, and a
formula-shaped forbidden entry -- mirroring tier 5's exclusion (which
applies the same `is_formula` check to both `ingredient` and
`forbidden_entry`) for the same reason: tier 2 already resolves formula
equality exhaustively and precisely via strict, order-independent parsing,
and an LLM asked to "reason" about whether two formulas (or a common name
and a formula) are the same substance can hallucinate a confident but wrong
answer. **Caught by manual full-batch verification, not by any unit test,
twice:**
- Ingredient side: with tier 6 live against a real Gemini call, sample
  P-2025-0022's `C6H8O7` (citric acid) was matched to forbidden `C8H10N4O2`
  (caffeine) -- two chemically unrelated formulas -- at confidence 1.0,
  flipping the sample from its correct Accepted status to a false Rejected.
- Forbidden-entry side: a live call matched ingredient `Aqua` (water, an
  INCI/trade name) to forbidden `H2O2` (hydrogen peroxide) at confidence
  1.0 -- water and hydrogen peroxide are not the same substance.

Automated per-matcher tests with a mocked client couldn't have caught
either: the mock only ever returns what the test tells it to.
Regression-guarded in
`tests/unit/test_llm_matcher.py::test_formula_shaped_ingredients_are_never_sent_to_the_llm`
and `test_formula_shaped_forbidden_entries_are_never_sent_to_the_llm`.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from app.domain.models import LlmUsage, MatchMethod, MatchResult
from app.domain.normalization.formula_parser import is_formula
from app.domain.normalization.text_normalizer import normalize_text
from app.infra.cache.llm_response_cache import LlmResponseCache
from app.infra.llm.base import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0


@dataclass
class LlmMatchOutcome:
    """Tier 6's result for one product: any matches found, plus token
    usage/cost for the single batched call actually made -- `usage` is None
    when every ingredient was served from cache (no call made) or the tier
    didn't run at all.
    """

    matches: list[MatchResult] = field(default_factory=list)
    usage: LlmUsage | None = None


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
    ) -> LlmMatchOutcome:
        if not ingredients or not forbidden_list:
            return LlmMatchOutcome()

        candidates = [ingredient for ingredient in ingredients if not is_formula(ingredient)]
        # Excluded on both sides -- see module docstring. A formula-shaped
        # *forbidden entry* is just as hallucination-prone as a formula-
        # shaped ingredient: live testing caught the LLM confidently matching
        # "Aqua" (water) to forbidden "H2O2" (hydrogen peroxide) at
        # confidence 1.0, the same class of bug as the citric-acid/caffeine
        # one below, just the mirror-image gap.
        non_formula_forbidden = [entry for entry in forbidden_list if not is_formula(entry)]
        if not candidates or not non_formula_forbidden:
            return LlmMatchOutcome()

        results_by_ingredient: dict[str, MatchResult | None] = {}
        to_query: list[str] = []
        for ingredient in candidates:
            hit, cached = self._cache.get(normalize_text(ingredient), forbidden_list_version)
            if hit:
                results_by_ingredient[ingredient] = cached
            else:
                to_query.append(ingredient)

        usage: LlmUsage | None = None
        if to_query:
            queried, usage = await self._query_and_cache(
                to_query, non_formula_forbidden, forbidden_list_version
            )
            results_by_ingredient.update(queried)

        matches = [
            result
            for ingredient in ingredients
            if (result := results_by_ingredient.get(ingredient)) is not None
        ]
        return LlmMatchOutcome(matches=matches, usage=usage)

    async def _query_and_cache(
        self,
        ingredients: list[str],
        forbidden_list: list[str],
        forbidden_list_version: str,
    ) -> tuple[dict[str, MatchResult | None], LlmUsage | None]:
        results: dict[str, MatchResult | None] = dict.fromkeys(ingredients)

        try:
            client_result = await asyncio.wait_for(
                self._client.match_ingredients(ingredients, forbidden_list),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fail open, an LLM outage must never break evaluation
            logger.warning("LLM matching tier failed open: %s", exc)
            for ingredient in ingredients:
                self._cache.set(normalize_text(ingredient), forbidden_list_version, None)
            return results, None

        for match in client_result.matches:
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
        return results, client_result.usage
