"""Shared matcher protocol for the tiered matching pipeline (ARCHITECTURE.md
Section 6). Each tier checks one (ingredient, forbidden_entry) pair in
isolation; the pipeline is responsible for iterating tiers/entries.
"""

from typing import Protocol

from app.domain.models import MatchResult


class Matcher(Protocol):
    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None: ...
