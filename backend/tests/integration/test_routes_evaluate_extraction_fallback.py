"""Integration test for the LLM extraction fallback wired end-to-end through
the real /evaluate route, with a mocked `LlmExtractionFallback` standing in
for Gemini.

No real Gemini call is made or credits spent -- `app.state.llm_extraction_fallback`
is overridden after app construction with an `LlmFallbackExtractor` backed by
a fake client, the same way `main.py` would wire a real
`PydanticAiExtractionFallback` when `ENABLE_LLM_MATCHING`/`GOOGLE_API_KEY` are
set (see `_build_llm_extraction_fallback` in app/main.py).
"""

from fastapi.testclient import TestClient

from app.domain.models import ExtractedProduct
from app.domain.parsing.llm_fallback import (
    LlmExtractionFallback,
    LlmExtractionOutcome,
    LlmFallbackExtractor,
)
from app.main import create_app


class _FakeExtractionClient(LlmExtractionFallback):
    async def extract(self, raw_text: str) -> LlmExtractionOutcome:
        return LlmExtractionOutcome(
            product=ExtractedProduct(
                product_name="Recovered Serum",
                ingredients=["Water", "Coumarin"],
                needs_llm_fallback=False,
            )
        )


def _client_with_extraction_fallback() -> TestClient:
    client = TestClient(create_app())
    client.__enter__()  # run lifespan so app.state is fully populated first
    client.app.state.llm_extraction_fallback = LlmFallbackExtractor(_FakeExtractionClient())
    return client


def test_file_with_no_ingredients_section_is_recovered_via_the_llm_fallback() -> None:
    client = _client_with_extraction_fallback()
    try:
        client.app.state.forbidden_list_repository.replace(["Coumarin"])
        text_body = b"Product Name: Mystery Serum\nDescription:\nNo ingredients listed here.\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.txt", text_body, "text/plain")}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["product_name"] == "Recovered Serum"
        assert body["status"] == "Rejected"
        assert body["reason"] == ["Contains Coumarin"]
    finally:
        client.__exit__(None, None, None)


def test_file_with_an_ingredients_section_never_reaches_the_fallback() -> None:
    client = _client_with_extraction_fallback()
    try:
        client.app.state.forbidden_list_repository.replace(["Coumarin"])
        text_body = b"Product Name: Clean Serum\nIngredients / Chemical Formulas:\n- Water\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.txt", text_body, "text/plain")}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["product_name"] == "Clean Serum"
        assert body["status"] == "Accepted"
    finally:
        client.__exit__(None, None, None)


def test_no_extraction_fallback_configured_rejects_an_unparseable_product() -> None:
    # A parser miss must never become a false Accepted safety verdict.
    with TestClient(create_app()) as client:
        client.app.state.llm_extraction_fallback = None
        client.app.state.forbidden_list_repository.replace(["Coumarin"])
        text_body = b"Product Name: Mystery Serum\nDescription:\nNo ingredients listed here.\n"

        response = client.post(
            "/api/evaluate", files={"files": ("product.txt", text_body, "text/plain")}
        )

        assert response.status_code == 422
        body = response.json()
        assert "Could not extract an ingredient list" in body["detail"]
