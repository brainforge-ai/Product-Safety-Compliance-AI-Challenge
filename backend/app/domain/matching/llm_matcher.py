"""Tier 6: async batched LLM matching (runs per product after tiers 1-5).

Not a MatchPipeline Matcher - async, product-scoped, and incompatible with
the shared sync pipeline instance under concurrent evaluation.
Formula-shaped ingredients and forbidden entries are excluded (tier 2 handles
those; LLM can hallucinate false formula matches).
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
        """Wrap an LLM client with caching and timeout fail-open behavior."""
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
        """Match ingredients the deterministic tiers missed, via LLM judgment.

        Sends unresolved names plus the full forbidden list to the LLM, which
        decides if two names refer to the same substance (synonyms, INCI names,
        trade names). Results are cached per ingredient and list version.
        """
        if not ingredients or not forbidden_list:
            return LlmMatchOutcome()

        # Formulas are handled by tier 2; LLMs can false-match chemical notation.
        candidates = [ingredient for ingredient in ingredients if not is_formula(ingredient)]
        non_formula_forbidden = [entry for entry in forbidden_list if not is_formula(entry)]
        if not candidates or not non_formula_forbidden:
            return LlmMatchOutcome()

        results_by_ingredient: dict[str, MatchResult | None] = {}
        to_query: list[str] = []
        # Split cache hits from ingredients that still need an LLM call.
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

        # Preserve caller ingredient order; skip formulas and non-matches.
        matches: list[MatchResult] = []
        for ingredient in ingredients:
            result = results_by_ingredient.get(ingredient)
            if result is not None:
                matches.append(result)
        return LlmMatchOutcome(matches=matches, usage=usage)

    async def _query_and_cache(
        self,
        ingredients: list[str],
        forbidden_list: list[str],
        forbidden_list_version: str,
    ) -> tuple[dict[str, MatchResult | None], LlmUsage | None]:
        """Call the LLM for uncached ingredients and store results in cache."""
        # Every queried ingredient gets an entry, even when the LLM finds no match.
        results: dict[str, MatchResult | None] = dict.fromkeys(ingredients)

        try:
            client_result = await asyncio.wait_for(
                self._client.match_ingredients(ingredients, forbidden_list),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fail open, an LLM outage must never break evaluation
            logger.warning("LLM matching tier failed open: %s", exc)
            # A transient outage is not a genuine "no match" verdict. Caching
            # it would silently suppress a real match until process restart.
            return results, None

        for match in client_result.matches:
            # Reject pairs the LLM invented that weren't in the request.
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

        # Store both matches and explicit non-matches for future cache lookups.
        for ingredient in ingredients:
            self._cache.set(normalize_text(ingredient), forbidden_list_version, results[ingredient])
        return results, client_result.usage
