"""Tier 4: acronym/abbreviation heuristic match (ARCHITECTURE.md Section 6).

Generic initials-based algorithm, not a hardcoded ingredient-to-acronym
lookup table (per the generalization principle in Section 3): given a
multi-word name, its "acronym" is the initials of each whitespace-separated
word. Checked in both directions since either the ingredient or the
forbidden entry could be the spelled-out form.

Known limitation: this only decomposes on whitespace, so a single-word
compound spelling (e.g. "Hydroxyanisole" as one word rather than "Hydroxy
Anisole") is not decomposed into further initials -- doing so generically
without a dataset-specific lookup would require morpheme-level chemical
nomenclature parsing, which is out of scope here.
"""

from app.domain.models import MatchMethod, MatchResult

_MIN_ACRONYM_LENGTH = 2
_MAX_ACRONYM_LENGTH = 6


def _looks_like_acronym(text: str) -> bool:
    stripped = text.strip()
    return (
        stripped.isalpha()
        and stripped.isupper()
        and _MIN_ACRONYM_LENGTH <= len(stripped) <= _MAX_ACRONYM_LENGTH
    )


def _is_multiword(text: str) -> bool:
    return len(text.strip().split()) >= 2


def _compute_initials(text: str) -> str:
    return "".join(word[0].upper() for word in text.strip().split() if word)


def _acronym_matches_name(acronym_candidate: str, name_candidate: str) -> bool:
    if not _looks_like_acronym(acronym_candidate):
        return False
    if not _is_multiword(name_candidate):
        return False
    return _compute_initials(name_candidate) == acronym_candidate.strip().upper()


class AcronymMatcher:
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        is_match = _acronym_matches_name(ingredient, forbidden_entry) or _acronym_matches_name(
            forbidden_entry, ingredient
        )
        if not is_match:
            return None

        return MatchResult(
            forbidden_ingredient=forbidden_entry,
            matched_text=ingredient,
            method=MatchMethod.ACRONYM,
            confidence=0.9,
        )
