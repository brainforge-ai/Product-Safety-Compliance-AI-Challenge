"""Matcher protocol: one (ingredient, forbidden_entry) pair per call."""

from typing import Protocol

from app.domain.models import MatchResult


class Matcher(Protocol):
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None: ...
