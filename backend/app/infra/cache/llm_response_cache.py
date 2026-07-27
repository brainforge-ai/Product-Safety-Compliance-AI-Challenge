"""In-memory cache for tier-6 LLM match responses (positive and negative).

Keyed by (normalized_ingredient, forbidden_list_version) so list uploads
invalidate stale verdicts without explicit eviction.
"""

from app.domain.models import MatchResult

CacheKey = tuple[str, str]


class LlmResponseCache:
    def __init__(self) -> None:
        """Create an in-memory cache keyed by ingredient and list version."""
        self._store: dict[CacheKey, MatchResult | None] = {}

    def get(
        self, normalized_ingredient: str, forbidden_list_version: str
    ) -> tuple[bool, MatchResult | None]:
        """Returns (hit, result). `result` is None both on a miss and on a
        cached negative outcome; check `hit` to distinguish the two.
        """
        key = (normalized_ingredient, forbidden_list_version)
        if key in self._store:
            return True, self._store[key]
        return False, None

    def set(
        self,
        normalized_ingredient: str,
        forbidden_list_version: str,
        result: MatchResult | None,
    ) -> None:
        """Store a match result or cached negative for an ingredient."""
        self._store[(normalized_ingredient, forbidden_list_version)] = result
