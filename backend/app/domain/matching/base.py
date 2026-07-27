"""Base class for sync pipeline matchers (tiers 1–5).

Each matcher answers one question for a single (ingredient, forbidden_entry) pair.
LlmMatcher is intentionally separate — async, batched, and not pipeline-compatible.
"""

from abc import ABC, abstractmethod

from app.domain.models import MatchResult


class Matcher(ABC):
    @abstractmethod
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        """Return a match when this strategy links ingredient to forbidden_entry."""
