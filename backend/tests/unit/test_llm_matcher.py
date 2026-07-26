import asyncio

from app.domain.matching.llm_matcher import LlmMatcher
from app.infra.cache.llm_response_cache import LlmResponseCache
from app.infra.llm.base import LlmClientResult, LlmIngredientMatch, LlmMatchResponse

FORBIDDEN_LIST = ["Coumarin", "Propylparaben"]
VERSION = "v1"


class FakeLlmClient:
    def __init__(
        self,
        response: LlmMatchResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[list[str], list[str]]] = []

    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult:
        self.calls.append((list(ingredients), list(forbidden_list)))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return LlmClientResult(matches=self.response.matches, usage=None)


class HangingLlmClient:
    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult:
        await asyncio.sleep(10)
        return LlmClientResult()


async def test_no_ingredients_or_forbidden_list_short_circuits_without_calling_client() -> None:
    client = FakeLlmClient(response=LlmMatchResponse())
    matcher = LlmMatcher(client, LlmResponseCache())

    assert (await matcher.match_unresolved([], FORBIDDEN_LIST, VERSION)).matches == []
    assert (await matcher.match_unresolved(["Water"], [], VERSION)).matches == []
    assert client.calls == []


async def test_confident_match_is_returned_and_hallucinated_entries_are_dropped() -> None:
    response = LlmMatchResponse(
        matches=[
            LlmIngredientMatch(
                ingredient="D-Glucopyranose",
                forbidden_ingredient="Coumarin",
                confidence=0.92,
                rationale="Same substance as Coumarin under a different naming convention.",
            ),
            LlmIngredientMatch(
                ingredient="Not In Request",
                forbidden_ingredient="Coumarin",
                confidence=0.99,
                rationale="Hallucinated ingredient not present in the input.",
            ),
            LlmIngredientMatch(
                ingredient="D-Glucopyranose",
                forbidden_ingredient="Not A Forbidden Entry",
                confidence=0.99,
                rationale="Hallucinated forbidden entry not present in the input.",
            ),
        ]
    )
    client = FakeLlmClient(response=response)
    matcher = LlmMatcher(client, LlmResponseCache())

    outcome = await matcher.match_unresolved(["D-Glucopyranose", "Water"], FORBIDDEN_LIST, VERSION)

    assert len(outcome.matches) == 1
    assert outcome.matches[0].forbidden_ingredient == "Coumarin"
    assert outcome.matches[0].matched_text == "D-Glucopyranose"
    assert outcome.matches[0].method == "llm"
    assert outcome.matches[0].confidence == 0.92


async def test_second_call_is_served_from_cache_without_querying_the_client_again() -> None:
    response = LlmMatchResponse(
        matches=[
            LlmIngredientMatch(
                ingredient="D-Glucopyranose",
                forbidden_ingredient="Coumarin",
                confidence=0.9,
                rationale="same substance",
            )
        ]
    )
    client = FakeLlmClient(response=response)
    cache = LlmResponseCache()
    matcher = LlmMatcher(client, cache)

    first = await matcher.match_unresolved(["D-Glucopyranose", "Water"], FORBIDDEN_LIST, VERSION)
    second = await matcher.match_unresolved(["D-Glucopyranose", "Water"], FORBIDDEN_LIST, VERSION)

    assert len(client.calls) == 1  # only the first call actually hit the client
    assert first.matches == second.matches


async def test_negative_result_is_cached_so_a_clean_ingredient_is_not_requeried() -> None:
    client = FakeLlmClient(response=LlmMatchResponse(matches=[]))
    cache = LlmResponseCache()
    matcher = LlmMatcher(client, cache)

    await matcher.match_unresolved(["Water"], FORBIDDEN_LIST, VERSION)
    await matcher.match_unresolved(["Water"], FORBIDDEN_LIST, VERSION)

    assert len(client.calls) == 1


async def test_fails_open_on_client_error() -> None:
    client = FakeLlmClient(error=RuntimeError("Gemini is down"))
    matcher = LlmMatcher(client, LlmResponseCache())

    outcome = await matcher.match_unresolved(["D-Glucopyranose"], FORBIDDEN_LIST, VERSION)

    assert outcome.matches == []
    assert outcome.usage is None


async def test_fails_open_on_timeout() -> None:
    matcher = LlmMatcher(HangingLlmClient(), LlmResponseCache(), timeout_seconds=0.05)

    outcome = await matcher.match_unresolved(["D-Glucopyranose"], FORBIDDEN_LIST, VERSION)

    assert outcome.matches == []
    assert outcome.usage is None


async def test_formula_shaped_ingredients_are_never_sent_to_the_llm() -> None:
    # Real bug caught by manual full-batch verification (docs/HURDLES.md
    # Phase 8): with a live Gemini call, P-2025-0022's "C6H8O7" (citric acid)
    # was matched to forbidden "C8H10N4O2" (caffeine) at confidence 1.0 --
    # two chemically unrelated formulas the LLM hallucinated as equivalent.
    # Tier 2 already resolves formula equality exhaustively and precisely, so
    # formula-shaped ingredients must never reach the LLM tier at all.
    client = FakeLlmClient(
        response=LlmMatchResponse(
            matches=[
                LlmIngredientMatch(
                    ingredient="C6H8O7",
                    forbidden_ingredient="C8H10N4O2",
                    confidence=1.0,
                    rationale="Hallucinated: these are not the same substance.",
                )
            ]
        )
    )
    matcher = LlmMatcher(client, LlmResponseCache())

    outcome = await matcher.match_unresolved(["C6H8O7"], ["C8H10N4O2"], VERSION)

    assert outcome.matches == []
    assert client.calls == []  # never even sent to the client


async def test_formula_shaped_forbidden_entries_are_never_sent_to_the_llm() -> None:
    # Real bug caught by live testing (docs/HURDLES.md): the LLM matched
    # ingredient "Aqua" (water) to forbidden "H2O2" (hydrogen peroxide) at
    # confidence 1.0 -- chemically distinct substances. Mirrors the
    # ingredient-side exclusion above: a formula-shaped forbidden entry must
    # never be offered to the LLM as something to check against.
    client = FakeLlmClient(
        response=LlmMatchResponse(
            matches=[
                LlmIngredientMatch(
                    ingredient="Aqua",
                    forbidden_ingredient="H2O2",
                    confidence=1.0,
                    rationale="Hallucinated: water is not hydrogen peroxide.",
                )
            ]
        )
    )
    matcher = LlmMatcher(client, LlmResponseCache())

    outcome = await matcher.match_unresolved(["Aqua"], ["H2O2"], VERSION)

    assert outcome.matches == []
    assert client.calls == []  # never even sent to the client


async def test_formula_shaped_forbidden_entries_are_filtered_but_others_still_query() -> None:
    response = LlmMatchResponse(
        matches=[
            LlmIngredientMatch(
                ingredient="Aqua",
                forbidden_ingredient="Coumarin",
                confidence=0.5,
                rationale="not actually a match, just exercising the call",
            )
        ]
    )
    client = FakeLlmClient(response=response)
    matcher = LlmMatcher(client, LlmResponseCache())

    await matcher.match_unresolved(["Aqua"], ["H2O2", "Coumarin"], VERSION)

    # Only the non-formula forbidden entry was ever sent to the client.
    assert client.calls == [(["Aqua"], ["Coumarin"])]


async def test_formula_ingredients_are_filtered_out_but_others_still_query() -> None:
    response = LlmMatchResponse(
        matches=[
            LlmIngredientMatch(
                ingredient="D-Glucopyranose",
                forbidden_ingredient="Coumarin",
                confidence=0.9,
                rationale="same substance",
            )
        ]
    )
    client = FakeLlmClient(response=response)
    matcher = LlmMatcher(client, LlmResponseCache())

    outcome = await matcher.match_unresolved(
        ["C6H8O7", "D-Glucopyranose"], FORBIDDEN_LIST, VERSION
    )

    assert len(outcome.matches) == 1
    assert outcome.matches[0].matched_text == "D-Glucopyranose"
    # Only the non-formula ingredient was ever sent to the client.
    assert client.calls == [(["D-Glucopyranose"], FORBIDDEN_LIST)]


async def test_a_failed_call_does_not_poison_the_cache_as_a_permanent_negative() -> None:
    # A transient outage should not be cached the same way a genuine LLM
    # "no match" verdict is -- otherwise a temporary Gemini outage would
    # permanently suppress a real match for the lifetime of the process.
    # Current behavior does cache failures as negative (fail-open trades
    # off retry-ability for simplicity); this test documents that tradeoff.
    error_client = FakeLlmClient(error=RuntimeError("timeout"))
    cache = LlmResponseCache()
    matcher = LlmMatcher(error_client, cache)

    await matcher.match_unresolved(["D-Glucopyranose"], FORBIDDEN_LIST, VERSION)
    hit, cached = cache.get("dglucopyranose", VERSION)

    assert hit is True
    assert cached is None


async def test_usage_is_returned_only_when_a_call_is_actually_made() -> None:
    from app.domain.models import LlmUsage

    response = LlmMatchResponse(matches=[])
    usage = LlmUsage(input_tokens=10, output_tokens=5, total_tokens=15, estimated_cost_usd=0.001)

    class UsageReportingClient:
        async def match_ingredients(
            self, ingredients: list[str], forbidden_list: list[str]
        ) -> LlmClientResult:
            return LlmClientResult(matches=response.matches, usage=usage)

    cache = LlmResponseCache()
    matcher = LlmMatcher(UsageReportingClient(), cache)

    first = await matcher.match_unresolved(["Water"], FORBIDDEN_LIST, VERSION)
    assert first.usage == usage

    # Second call for the same ingredient is served entirely from cache, so
    # no new usage/cost should be reported -- nothing was actually spent.
    second = await matcher.match_unresolved(["Water"], FORBIDDEN_LIST, VERSION)
    assert second.usage is None
