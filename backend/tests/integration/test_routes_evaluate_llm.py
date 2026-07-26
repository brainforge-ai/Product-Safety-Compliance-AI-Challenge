"""Integration test for tier 6 (LLM matching) wired end-to-end through the
real /evaluate route, with a mocked LLMClient standing in for Gemini.

No real Gemini call is made or credits spent -- `app.state.llm_matcher` is
overridden after app construction with an `LlmMatcher` backed by a fake
client, exactly the way `main.py` would wire a real `PydanticAiLlmClient`
when `ENABLE_LLM_MATCHING`/`GOOGLE_API_KEY` are set (ARCHITECTURE.md Section
7, 13).
"""

from fastapi.testclient import TestClient

from app.domain.matching.llm_matcher import LlmMatcher
from app.infra.cache.llm_response_cache import LlmResponseCache
from app.infra.llm.base import LlmIngredientMatch, LlmMatchResponse
from app.main import create_app


class _FakeLlmClient:
    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmMatchResponse:
        if "D-Glucopyranose" in ingredients and "Glucose" in forbidden_list:
            return LlmMatchResponse(
                matches=[
                    LlmIngredientMatch(
                        ingredient="D-Glucopyranose",
                        forbidden_ingredient="Glucose",
                        confidence=0.93,
                        rationale="Same substance under a different naming convention.",
                    )
                ]
            )
        return LlmMatchResponse()


def _client_with_llm_matcher() -> TestClient:
    client = TestClient(create_app())
    client.__enter__()  # run lifespan so app.state is fully populated first
    client.app.state.llm_matcher = LlmMatcher(_FakeLlmClient(), LlmResponseCache())
    return client


def test_llm_tier_catches_a_naming_variant_that_tiers_1_5_miss() -> None:
    client = _client_with_llm_matcher()
    try:
        client.app.state.forbidden_list_repository.replace(["Glucose"])
        csv_body = b"Product Name,Ingredients\nSynthetic Serum,Water;D-Glucopyranose\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.csv", csv_body, "text/csv")}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "Rejected"
        assert body["reason"] == ["Contains Glucose"]
        assert body["matches"][0]["method"] == "llm"
    finally:
        client.__exit__(None, None, None)


def test_llm_tier_does_not_run_when_nothing_is_unresolved() -> None:
    client = _client_with_llm_matcher()
    try:
        client.app.state.forbidden_list_repository.replace(["Coumarin"])
        csv_body = b"Product Name,Ingredients\nSynthetic Serum,Water\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.csv", csv_body, "text/csv")}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "Accepted"
    finally:
        client.__exit__(None, None, None)


def test_no_llm_matcher_configured_leaves_naming_variant_unresolved() -> None:
    # Baseline: without tier 6 wired in (the default -- ENABLE_LLM_MATCHING
    # is false), the same naming-convention variant is NOT caught. This is
    # the documented gap tiers 1-5 cannot close (see embedding_matcher.py).
    with TestClient(create_app()) as client:
        client.app.state.forbidden_list_repository.replace(["Glucose"])
        csv_body = b"Product Name,Ingredients\nSynthetic Serum,Water;D-Glucopyranose\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.csv", csv_body, "text/csv")}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "Accepted"
