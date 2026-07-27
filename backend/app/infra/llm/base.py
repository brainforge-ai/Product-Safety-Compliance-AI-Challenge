"""LLMClient protocol and structured output schema for tier 6."""

from typing import Protocol

from pydantic import BaseModel, Field

from app.domain.models import LlmUsage


class LlmIngredientMatch(BaseModel):
    """One ingredient/forbidden-entry pair the LLM judged to be the same substance."""

    ingredient: str
    forbidden_ingredient: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class LlmMatchResponse(BaseModel):
    matches: list[LlmIngredientMatch] = Field(default_factory=list)


class LlmClientResult(BaseModel):
    matches: list[LlmIngredientMatch] = Field(default_factory=list)
    usage: LlmUsage | None = None


class LLMClient(Protocol):
    async def match_ingredients(
        self, ingredients: list[str], forbidden_list: list[str]
    ) -> LlmClientResult: ...
