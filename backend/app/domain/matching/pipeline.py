"""Escalating matcher pipeline: tiers run in order, first match wins."""

from app.domain.matching.base import Matcher
from app.domain.models import MatchResult


class MatchPipeline:
    def __init__(self, matchers: list[Matcher]) -> None:
        """Register matchers in escalation order (first match wins)."""
        self._matchers = matchers

    def match_ingredient(self, ingredient: str, forbidden_list: list[str]) -> MatchResult | None:
        """Return the first match found across matchers and forbidden entries."""
        for matcher in self._matchers:
            for forbidden_entry in forbidden_list:
                result = matcher.match(ingredient, forbidden_entry)
                if result is not None:
                    return result
        return None
