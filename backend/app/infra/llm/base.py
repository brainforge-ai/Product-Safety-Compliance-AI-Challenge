"""LLMClient protocol and structured output schema for tier 6
(ARCHITECTURE.md Section 7).

`LlmMatchResponse` is the `output_type` handed to the Pydantic AI `Agent` for
validated structured output; it lives here (rather than in
`pydantic_ai_client.py`) so the protocol and its response shape travel
together, independent of which concrete adapter implements `LLMClient`.
Defining it with plain Pydantic (already a trusted core dependency) keeps
this module importable without pulling in `pydantic_ai` itself, so
`domain/matching/llm_matcher.py` can depend on the protocol without ever
importing the concrete adapter.
"""

from typing import Protocol

from pydantic import BaseModel, Field


class LlmIngredientMatch(BaseModel):
    """One ingredient/forbidden-entry pair the LLM judged to be the same substance."""

    ingredient: str
    forbidden_ingredient: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class LlmMatchResponse(BaseModel):
    matches: list[LlmIngredientMatch] = Field(default_factory=list)


class LLMClient(Protocol):
    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmMatchResponse: ...
