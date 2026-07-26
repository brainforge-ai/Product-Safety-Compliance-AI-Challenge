"""Pydantic AI + Gemini adapter for `LlmExtractionFallback`
(`domain/parsing/llm_fallback.py`).

Mirrors `pydantic_ai_client.py`'s `GoogleProvider`/`GoogleModel` construction
(same rationale: explicit API key from `Settings`, `LLM_MODEL` never
hardcoded) but targets a distinct, lean output schema instead of
`ExtractedProduct` directly -- `needs_llm_fallback` is bookkeeping for the
parsing layer, not a field the model should be asked to fill in.
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import Settings
from app.domain.models import ExtractedProduct
from app.domain.parsing.llm_fallback import LlmExtractionOutcome
from app.infra.llm.model_naming import strip_provider_prefix
from app.infra.llm.usage import usage_from_run

_SYSTEM_PROMPT = (
    "You are extracting structured product-label fields from raw text "
    "pulled from a PDF, image (OCR), or text file -- a regex-based parser "
    "already tried and failed to find an ingredients list in it, so the "
    "formatting is likely irregular. Extract product_id, product_name, "
    "sku, description, and the full list of ingredients exactly as "
    "written, one entry per ingredient. If a field is genuinely absent "
    "from the text, leave it null (or an empty list for ingredients) -- "
    "never invent values."
)


class _ExtractedFields(BaseModel):
    product_id: str | None = None
    product_name: str
    sku: str | None = None
    description: str | None = None
    ingredients: list[str] = Field(default_factory=list)


class PydanticAiExtractionFallback:
    def __init__(self, settings: Settings) -> None:
        self._model_ref = strip_provider_prefix(settings.llm_model)
        provider = GoogleProvider(api_key=settings.google_api_key)
        model = GoogleModel(self._model_ref, provider=provider)
        self._agent = Agent(model, output_type=_ExtractedFields, system_prompt=_SYSTEM_PROMPT)

    async def extract(self, raw_text: str) -> LlmExtractionOutcome:
        result = await self._agent.run(raw_text)
        fields = result.output
        product = ExtractedProduct(
            product_id=fields.product_id,
            product_name=fields.product_name,
            sku=fields.sku,
            description=fields.description,
            ingredients=fields.ingredients,
            needs_llm_fallback=False,
        )
        usage = usage_from_run(result.usage, self._model_ref)
        return LlmExtractionOutcome(product=product, usage=usage)
