"""Tier 4: acronym/abbreviation heuristic match (initials of multi-word names)."""

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
