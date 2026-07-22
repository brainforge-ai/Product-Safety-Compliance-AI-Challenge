"""Composes matcher tiers into the escalating pipeline described in
ARCHITECTURE.md Section 6: for a given ingredient, tiers run in order and
the pipeline stops at the first confident match found against any
forbidden entry. Built to accept an arbitrary ordered list of matchers so
tiers 5-6 can be registered later (Phase 8) without changing this class.
"""

from app.domain.matching.base import Matcher
from app.domain.models import MatchResult


class MatchPipeline:
    def __init__(self, matchers: list[Matcher]) -> None:
        self._matchers = matchers

    def match_ingredient(self, ingredient: str, forbidden_list: list[str]) -> MatchResult | None:
        for matcher in self._matchers:
            for forbidden_entry in forbidden_list:
                result = matcher.match(ingredient, forbidden_entry)
                if result is not None:
                    return result
        return None
