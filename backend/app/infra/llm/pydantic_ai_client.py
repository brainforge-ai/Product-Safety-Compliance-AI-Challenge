"""Pydantic AI + Gemini adapter for the LLMClient protocol.

API key is passed to GoogleProvider from Settings explicitly — pydantic-settings
loads .env into Settings only, not the process environment.
"""

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import Settings
from app.infra.llm.base import LlmClientResult, LlmMatchResponse
from app.infra.llm.model_naming import strip_provider_prefix
from app.infra.llm.usage import usage_from_run

_SYSTEM_PROMPT = (
    "You are a chemical ingredient safety compliance assistant. Given a list "
    "of product ingredients and a list of forbidden ingredients, identify "
    "which product ingredients refer to the SAME substance as a forbidden "
    "ingredient, even when named differently -- an INCI name, a trade name, "
    "a CAS synonym, or a different naming convention for the same chemical "
    "(for example, 'Glucose' and 'D-Glucopyranose' are the same substance). "
    "Only report a match when you are confident the two names refer to the "
    "same substance; do not match merely related or similarly-spelled "
    "substances. For every match, return the exact product ingredient text "
    "and the exact forbidden ingredient text as given in the input, a "
    "confidence between 0 and 1, and a brief rationale."
)


def _build_prompt(ingredients: list[str], forbidden_list: list[str]) -> str:
    """Format ingredients and forbidden entries for the LLM match prompt."""
    ingredients_block = "\n".join(f"- {i}" for i in ingredients)
    forbidden_block = "\n".join(f"- {f}" for f in forbidden_list)
    return (
        "Product ingredients to check:\n"
        f"{ingredients_block}\n\n"
        "Forbidden ingredients list:\n"
        f"{forbidden_block}"
    )


class PydanticAiLlmClient:
    def __init__(self, settings: Settings) -> None:
        """Configure a Gemini-backed Pydantic AI agent for ingredient matching."""
        self._model_ref = strip_provider_prefix(settings.llm_model)
        provider = GoogleProvider(api_key=settings.google_api_key)
        model = GoogleModel(self._model_ref, provider=provider)
        self._agent = Agent(model, output_type=LlmMatchResponse, system_prompt=_SYSTEM_PROMPT)

    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult:
        """Ask the LLM which ingredients match forbidden entries."""
        result = await self._agent.run(_build_prompt(ingredients, forbidden_list))
        return LlmClientResult(
            matches=result.output.matches,
            usage=usage_from_run(result.usage, self._model_ref),
        )
