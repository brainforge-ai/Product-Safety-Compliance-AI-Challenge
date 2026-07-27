"""Tier 3: rapidfuzz fuzzy string match on normalized text.

Threshold >=90 to avoid false positives on short or similar-but-distinct names.
"""

from rapidfuzz import fuzz

from app.domain.matching.base import Matcher
from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.text_normalizer import normalize_text

DEFAULT_FUZZY_THRESHOLD = 90.0


class FuzzyMatcher(Matcher):
    def __init__(self, threshold: float = DEFAULT_FUZZY_THRESHOLD) -> None:
        """Set the minimum rapidfuzz ratio required to count as a match."""
        self._threshold = threshold

    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        """Match when normalized strings are highly similar but not identical.

        Uses rapidfuzz character-level ratio on normalized text. Requires
        score >= 90 to catch typos/OCR noise without matching distinct names.
        """
        normalized_ingredient = normalize_text(ingredient)
        normalized_forbidden = normalize_text(forbidden_entry)
        if not normalized_ingredient or not normalized_forbidden:
            return None

        score = fuzz.ratio(normalized_ingredient, normalized_forbidden)
        if score < self._threshold:
            return None

        return MatchResult(
            forbidden_ingredient=forbidden_entry,
            matched_text=ingredient,
            method=MatchMethod.FUZZY,
            confidence=min(score / 100.0, 1.0),
        )
