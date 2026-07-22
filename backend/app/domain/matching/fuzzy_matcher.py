"""Tier 3: rapidfuzz fuzzy string match on normalized text (ARCHITECTURE.md
Section 6).

The threshold is deliberately conservative (>=90). A looser threshold that
would catch loose semantic variants with no lexical overlap (e.g. the
README's `Glucose` vs `D-Glucopyranose` example) also catches closer but
genuinely distinct real ingredients: every standard string-similarity
metric tried (rapidfuzz `ratio`/`partial_ratio`/`token_sort_ratio`/
`token_set_ratio`/`WRatio`, Levenshtein distance, Jaro-Winkler) scores
`Glucose` vs `D-Glucopyranose` (~0.65-0.76) *lower* than real sample
P-2025-0024's `Sodium Laureth Sulfate` vs the forbidden `Sodium Lauryl
Sulfate` (~0.85-0.91) — a pair that must NOT match. No fuzzy threshold can
thread both; protecting the real sample from a false reject wins over
catching the synthetic doc example (see ARCHITECTURE.md Section 6 and
docs/IMPLEMENTATION_PLAN.md Phase 5/8 notes for the full analysis).
"""

from rapidfuzz import fuzz

from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.text_normalizer import normalize_text

DEFAULT_FUZZY_THRESHOLD = 90.0


class FuzzyMatcher:
    def __init__(self, threshold: float = DEFAULT_FUZZY_THRESHOLD) -> None:
        self._threshold = threshold

    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
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
