"""In-memory cache for tier-6 LLM match responses, keyed by
`(normalized_ingredient, forbidden_list_version)` (ARCHITECTURE.md Section 7).

Caches BOTH positive and negative ("no match") outcomes: an ingredient the
LLM confidently ruled out should not be re-queried on every request just
because it produced no `MatchResult`. The version component invalidates
stale verdicts the moment the forbidden list changes -- a fresh version hash
means every entry keyed to the old version is simply never looked up again.
"""

from app.domain.models import MatchResult

CacheKey = tuple[str, str]


class LlmResponseCache:
    def __init__(self) -> None:
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
        self._store[(normalized_ingredient, forbidden_list_version)] = result
