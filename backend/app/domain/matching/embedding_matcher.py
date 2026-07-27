"""Tier 5: sentence-embedding cosine-similarity match.

Encoder is injected for testability; formula-shaped strings are skipped
(tier 2 handles those; embedding formula text causes false positives).
Threshold 0.90 is conservative — looser values false-match distinct real ingredients.
"""

from app.domain.matching.base import Matcher
from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.formula_parser import is_formula
from app.domain.normalization.text_normalizer import normalize_text
from app.infra.embeddings.base import Encoder

DEFAULT_EMBEDDING_THRESHOLD = 0.90


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingMatcher(Matcher):
    def __init__(self, encoder: Encoder, threshold: float = DEFAULT_EMBEDDING_THRESHOLD) -> None:
        """Configure embedding similarity matching with a cosine threshold."""
        self._encoder = encoder
        self._threshold = threshold
        self._embedding_cache: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        """Return a cached sentence embedding for normalized text."""
        if text not in self._embedding_cache:
            self._embedding_cache[text] = self._encoder.encode([text])[0]
        return self._embedding_cache[text]

    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
        """Match when sentence embeddings are semantically close.

        Encodes both normalized strings, then compares cosine similarity.
        Skips formula-shaped text (tier 2 handles those). Requires similarity
        >= 0.90 to match synonyms without false positives on unrelated names.
        """
        if is_formula(ingredient) or is_formula(forbidden_entry):
            return None

        normalized_ingredient = normalize_text(ingredient)
        normalized_forbidden = normalize_text(forbidden_entry)
        if not normalized_ingredient or not normalized_forbidden:
            return None

        similarity = _cosine_similarity(
            self._embed(normalized_ingredient), self._embed(normalized_forbidden)
        )
        if similarity < self._threshold:
            return None

        return MatchResult(
            forbidden_ingredient=forbidden_entry,
            matched_text=ingredient,
            method=MatchMethod.EMBEDDING,
            confidence=max(0.0, min(similarity, 1.0)),
        )
