"""In-memory cache for tier-6 LLM match responses (positive and negative).

Keyed by (normalized_ingredient, forbidden_list_version) so list uploads
invalidate stale verdicts without explicit eviction.
"""

from collections import OrderedDict
from threading import Lock

from app.domain.models import MatchResult

CacheKey = tuple[str, str]


class LlmResponseCache:
    def __init__(self, max_entries: int = 4096) -> None:
        """Create an in-memory cache keyed by ingredient and list version."""
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._store: OrderedDict[CacheKey, MatchResult | None] = OrderedDict()
        self._lock = Lock()

    def get(
        self, normalized_ingredient: str, forbidden_list_version: str
    ) -> tuple[bool, MatchResult | None]:
        """Returns (hit, result). `result` is None both on a miss and on a
        cached negative outcome; check `hit` to distinguish the two.
        """
        key = (normalized_ingredient, forbidden_list_version)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return True, self._store[key]
            return False, None

    def set(
        self,
        normalized_ingredient: str,
        forbidden_list_version: str,
        result: MatchResult | None,
    ) -> None:
        """Store a match result or cached negative for an ingredient."""
        key = (normalized_ingredient, forbidden_list_version)
        with self._lock:
            self._store[key] = result
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
