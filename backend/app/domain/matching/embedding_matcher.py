"""Tier 5 (optional): local sentence-embedding cosine-similarity match
(ARCHITECTURE.md Section 6).

The encoder is injected (`Encoder` protocol) rather than importing
`sentence-transformers` directly, so this class stays testable with a fake,
fully offline, and so `pytest` never depends on the ~90MB MiniLM download
(ARCHITECTURE.md Section 13). The real model lives behind a lazy singleton
loader in `infra/embeddings/sentence_transformer_encoder.py`, wired in by
`main.py` only when `ENABLE_EMBEDDING_MATCHING` is set.

Formula-shaped ingredients are skipped entirely (`is_formula`): tier 2
already resolves formulas exhaustively and precisely via order-independent
parsing, and empirically (see below) treating formula strings as text for
embedding purposes is actively harmful, not just redundant.

**Empirically verified in Phase 8 (see docs/HURDLES.md and
docs/IMPLEMENTATION_PLAN.md Phase 8 notes for the full numbers):** the
challenge README's own worked example -- `Glucose` vs `D-Glucopyranose` as a
naming-convention variation -- scores only ~0.35 cosine similarity with the
real `all-MiniLM-L6-v2` model. That is *lower* than the similarity between
several genuinely distinct ingredient pairs found in the 6 samples that must
stay Accepted: `Sodium Metabisulfite` vs forbidden `Sodium Lauryl Sulfate`
scores ~0.75, and (before formula exclusion) `C6H8O7` (citric acid) vs
forbidden `C6H6` scores ~0.85 purely from character overlap between formula
strings. This is the same inversion Phase 5 found with fuzzy matching: no
threshold can catch the README's example without also false-rejecting a real
Accepted sample, so the threshold is set conservatively (0.90) to protect the
real samples, same precedent as `fuzzy_matcher.py`. Tier 6 (LLM reasoning)
remains the only tier that can plausibly catch this class of example.
"""

from typing import Protocol

from app.domain.models import MatchMethod, MatchResult
from app.domain.normalization.formula_parser import is_formula
from app.domain.normalization.text_normalizer import normalize_text

DEFAULT_EMBEDDING_THRESHOLD = 0.90


class Encoder(Protocol):
    def __call__(self, texts: list[str]) -> list[list[float]]: ...


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingMatcher:
    def __init__(self, encoder: Encoder, threshold: float = DEFAULT_EMBEDDING_THRESHOLD) -> None:
        self._encoder = encoder
        self._threshold = threshold
        self._embedding_cache: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        if text not in self._embedding_cache:
            self._embedding_cache[text] = self._encoder([text])[0]
        return self._embedding_cache[text]

    def match(self, ingredient: str, forbidden_entry: str) -> MatchResult | None:
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
