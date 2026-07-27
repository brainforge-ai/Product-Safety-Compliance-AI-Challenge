"""Integration test for tier 6 (LLM matching) wired end-to-end through the
real /evaluate route, with a mocked LLMClient standing in for Gemini.

No real Gemini call is made or credits spent -- `app.state.llm_matcher` is
overridden after app construction with an `LlmMatcher` backed by a fake
client, exactly the way `main.py` would wire a real `PydanticAiLlmClient`
when `ENABLE_LLM_MATCHING`/`GOOGLE_API_KEY` are set (ARCHITECTURE.md Section
7, 13).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.matching.llm_matcher import LlmMatcher
from app.infra.cache.llm_response_cache import LlmResponseCache
from app.infra.llm.base import LLMClient, LlmClientResult, LlmIngredientMatch
from app.main import create_app

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"

# Mirrors the real repo-root forbidden_ingredients.csv (13 entries), inlined
# rather than read from disk so this test doesn't depend on that file's
# content staying exactly as-is.
REAL_FORBIDDEN_LIST = [
    "1,4-Dioxane",
    "BHA",
    "BHT",
    "Butylparaben",
    "C6H6",
    "C8H10N4O2",
    "Coumarin",
    "Formaldehyde",
    "H2O2",
    "Methylparaben",
    "Propylparaben",
    "Sodium Lauryl Sulfate",
    "Triclosan",
]


class _FakeLlmClient(LLMClient):
    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult:
        if "D-Glucopyranose" in ingredients and "Glucose" in forbidden_list:
            return LlmClientResult(
                matches=[
                    LlmIngredientMatch(
                        ingredient="D-Glucopyranose",
                        forbidden_ingredient="Glucose",
                        confidence=0.93,
                        rationale="Same substance under a different naming convention.",
                    )
                ]
            )
        if "Butyl 4-hydroxybenzoate" in ingredients and "Butylparaben" in forbidden_list:
            return LlmClientResult(
                matches=[
                    LlmIngredientMatch(
                        ingredient="Butyl 4-hydroxybenzoate",
                        forbidden_ingredient="Butylparaben",
                        confidence=0.95,
                        rationale="Butyl 4-hydroxybenzoate is the ester/IUPAC-style name for "
                        "the paraben ingredient Butylparaben.",
                    )
                ]
            )
        return LlmClientResult()


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


def test_llm_tier_catches_a_naming_variant_in_a_real_product_file() -> None:
    # Same scenario as the CSV-based test above, but through a real product
    # file in the standard sample format (Product ID/Name/SKU/Description/
    # Ingredients section) rather than a synthetic inline CSV row -- proves
    # the LLM path also works after the real text extractor and product
    # parser, not just the CSV row-mapping path. Fixture is not part of the
    # provided sample dataset; see its own header comment.
    client = _client_with_llm_matcher()
    try:
        client.app.state.forbidden_list_repository.replace(["Glucose"])
        path = FIXTURES_DIR / "demo_llm_required_example.txt"

        with path.open("rb") as f:
            response = client.post(
                "/api/evaluate", files={"files": (path.name, f, "text/plain")}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "Rejected"
        assert body["reason"] == ["Contains Glucose"]
        assert body["matches"][0]["method"] == "llm"
        assert body["matches"][0]["matched_text"] == "D-Glucopyranose"
    finally:
        client.__exit__(None, None, None)


def test_llm_tier_catches_a_naming_variant_against_the_real_forbidden_list() -> None:
    # Companion to the two Glucose-based tests above, but deliberately
    # against the REAL 13-entry forbidden list rather than a custom
    # single-entry one -- this is the "fail case that fits alongside the
    # other [real sample] files" scenario: no forbidden-list swap needed,
    # so this fixture could be uploaded together with any of the 30 real
    # sample files in one batch. rapidfuzz-confirmed (ratio/token_sort/
    # token_set/WRatio, see docs/HURDLES.md Phase 10) that "Butyl
    # 4-hydroxybenzoate" scores well under the production fuzzy threshold
    # against every one of the 13 real entries, and the real tiers 1-4
    # pipeline returns no match for it -- only tier 6 resolves it.
    client = _client_with_llm_matcher()
    try:
        client.app.state.forbidden_list_repository.replace(REAL_FORBIDDEN_LIST)
        path = FIXTURES_DIR / "demo_llm_required_real_list.txt"

        with path.open("rb") as f:
            response = client.post(
                "/api/evaluate", files={"files": (path.name, f, "text/plain")}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "Rejected"
        assert body["reason"] == ["Contains Butylparaben"]
        assert body["matches"][0]["method"] == "llm"
        assert body["matches"][0]["matched_text"] == "Butyl 4-hydroxybenzoate"
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
    # `llm_matcher` is set to None explicitly rather than relying on ambient
    # `.env` state (ENABLE_LLM_MATCHING defaulting to false) -- a local .env
    # with the flag flipped on for live testing must never make this
    # baseline silently spend real Gemini credits.
    with TestClient(create_app()) as client:
        client.app.state.llm_matcher = None
        client.app.state.forbidden_list_repository.replace(["Glucose"])
        csv_body = b"Product Name,Ingredients\nSynthetic Serum,Water;D-Glucopyranose\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.csv", csv_body, "text/csv")}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "Accepted"
