"""Tier 1: normalized exact string match."""

from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.text_normalizer import normalize_text


class ExactMatcher:
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        normalized_ingredient = normalize_text(ingredient)
        if not normalized_ingredient:
            return None
        if normalized_ingredient != normalize_text(forbidden_entry):
            return None

        return MatchResult(
            forbidden_ingredient=forbidden_entry,
            matched_text=ingredient,
            method=MatchMethod.EXACT,
            confidence=1.0,
        )
