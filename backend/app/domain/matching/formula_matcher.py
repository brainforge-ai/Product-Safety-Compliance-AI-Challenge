"""Tier 2: molecular formula canonicalization match with OCR corruption recovery."""

from collections.abc import Iterator
from itertools import combinations

from app.domain.matching.base import Matcher
from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.formula_parser import formulas_equal, parse_formula

# Tesseract OCR misreads within formulas: O→0, C→€.
_OCR_CORRECTIONS = {"0": "O", "€": "C"}

# Caps how many misreads we try fixing in one variant; formulas here are short.
_MAX_CORRECTIONS = 4

_CORRECTED_CONFIDENCE = 0.9


def _ocr_misread_indices(text: str) -> list[int]:
    """Indices of characters that might be a misread O (0) or C (€)."""
    return [index for index, char in enumerate(text) if char in _OCR_CORRECTIONS]


def _apply_ocr_fixes(text: str, fix_at: tuple[int, ...]) -> str:
    """Return a copy of text with 0→O and €→C applied at the given indices."""
    chars = list(text)
    for index in fix_at:
        chars[index] = _OCR_CORRECTIONS[chars[index]]
    return "".join(chars)


def _iter_corrected_variants(text: str) -> Iterator[str]:
    """Yield variants that fix one or more OCR misreads.

    For "H202" this yields "H2O2". For multiple ambiguous characters we try
    every combination of fixes, up to _MAX_CORRECTIONS per variant.
    """
    misread_indices = _ocr_misread_indices(text)
    max_fixes = min(len(misread_indices), _MAX_CORRECTIONS)

    for fix_count in range(1, max_fixes + 1):
        for indices_to_fix in combinations(misread_indices, fix_count):
            yield _apply_ocr_fixes(text, indices_to_fix)


def _formula_result(
    ingredient: str, forbidden_entry: str, *, confidence: float
) -> MatchResult:
    return MatchResult(
        forbidden_ingredient=forbidden_entry,
        matched_text=ingredient,
        method=MatchMethod.FORMULA,
        confidence=confidence,
    )


class FormulaMatcher(Matcher):
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        """Match when both sides represent the same molecular formula.

        Only runs when the forbidden entry parses as a formula. Compares
        element counts in any order (H2O2 == O2H2). If the ingredient text
        looks OCR-corrupted (0→O, €→C), tries corrected variants before giving up.
        """
        forbidden_parsed = parse_formula(forbidden_entry)
        if forbidden_parsed is None:
            return None  # this tier only applies when the forbidden entry is itself a formula

        if formulas_equal(ingredient, forbidden_entry):
            return _formula_result(ingredient, forbidden_entry, confidence=1.0)

        for corrected in _iter_corrected_variants(ingredient):
            if parse_formula(corrected) == forbidden_parsed:
                return _formula_result(
                    ingredient, forbidden_entry, confidence=_CORRECTED_CONFIDENCE
                )

        return None
