"""Pydantic AI + Gemini adapter for the `LLMClient` protocol
(ARCHITECTURE.md Section 7).

Decision: Pydantic AI over LiteLLM/Vercel AI SDK -- see ARCHITECTURE.md
Section 7 for the full writeup (LiteLLM's March 2026 supply-chain
compromise, a thinner dependency surface via Google's official
`google-genai` SDK, and native validated structured output via
`output_type`).

The API key is passed to `GoogleProvider` explicitly from our own `Settings`
object rather than relying on `GoogleProvider`'s automatic `GOOGLE_API_KEY`/
`GEMINI_API_KEY` environment-variable pickup: `pydantic-settings` loads
`.env` into the `Settings` model only, it does not itself set the process
environment, so relying on the implicit pickup would silently break whenever
a key is supplied only via `.env` and not also exported into the shell.
`LLM_MODEL` is never hardcoded, always read from `settings.llm_model`, per
ARCHITECTURE.md Section 7.
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
        self._model_ref = strip_provider_prefix(settings.llm_model)
        provider = GoogleProvider(api_key=settings.google_api_key)
        model = GoogleModel(self._model_ref, provider=provider)
        self._agent = Agent(model, output_type=LlmMatchResponse, system_prompt=_SYSTEM_PROMPT)

    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult:
        result = await self._agent.run(_build_prompt(ingredients, forbidden_list))
        return LlmClientResult(
            matches=result.output.matches,
            usage=usage_from_run(result.usage, self._model_ref),
        )
