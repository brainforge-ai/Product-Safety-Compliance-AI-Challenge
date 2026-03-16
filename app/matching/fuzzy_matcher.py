"""Fuzzy matching utilities."""

from rapidfuzz import fuzz

from ..config import FORBIDDEN_INGREDIENTS


def fuzzy_match(ingredients):
    """
    Fuzzy-match extracted ingredients against the forbidden ingredient list.
    Returns a de-duplicated list of forbidden ingredients that matched above a threshold.
    """
    matches = []

    for ing in ingredients:
        for forbidden in FORBIDDEN_INGREDIENTS:
            score = fuzz.ratio(ing, forbidden)

            if score > 85:
                matches.append(forbidden)

    return list(set(matches))
