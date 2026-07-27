"""Tier 2: molecular formula canonicalization match with OCR corruption recovery."""

from collections.abc import Iterator
from itertools import combinations

from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.formula_parser import formulas_equal, parse_formula

# Tesseract OCR misreads within formulas: O→0, C→€.
_OCR_CORRECTIONS = {"0": "O", "€": "C"}

# Caps the combinatorial search over which ambiguous characters to correct;
# real formulas in this domain are short, so this is never a binding limit.
_MAX_CORRECTIONS = 4

_CORRECTED_CONFIDENCE = 0.9


def _iter_corrected_variants(text: str) -> Iterator[str]:
    positions = [i for i, ch in enumerate(text) if ch in _OCR_CORRECTIONS]
    limit = min(len(positions), _MAX_CORRECTIONS)
    for r in range(1, limit + 1):
        for combo in combinations(positions, r):
            chars = list(text)
            for i in combo:
                chars[i] = _OCR_CORRECTIONS[chars[i]]
            yield "".join(chars)


class FormulaMatcher:
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        forbidden_parsed = parse_formula(forbidden_entry)
        if forbidden_parsed is None:
            return None  # this tier only applies when the forbidden entry is itself a formula

        if formulas_equal(ingredient, forbidden_entry):
            return MatchResult(
                forbidden_ingredient=forbidden_entry,
                matched_text=ingredient,
                method=MatchMethod.FORMULA,
                confidence=1.0,
            )

        for variant in _iter_corrected_variants(ingredient):
            if parse_formula(variant) == forbidden_parsed:
                return MatchResult(
                    forbidden_ingredient=forbidden_entry,
                    matched_text=ingredient,
                    method=MatchMethod.FORMULA,
                    confidence=_CORRECTED_CONFIDENCE,
                )

        return None
