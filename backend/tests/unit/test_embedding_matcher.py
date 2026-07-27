from app.domain.matching.embedding_matcher import EmbeddingMatcher
from app.infra.embeddings.base import Encoder

# Fixed toy vector space: an ingredient and forbidden entry embed identically
# (or nearly so) only when their fake vector matches, so tests are fully
# deterministic and never touch the real sentence-transformers model.
_VECTORS = {
    "coumarinn": [1.0, 0.0],
    "coumarin": [1.0, 0.0],
    "water": [0.0, 1.0],
    "triclosan": [-1.0, 0.0],
    "glucose": [1.0, 0.0],
    "dglucopyranose": [0.6, 0.8],  # cosine similarity 0.6 against "glucose"
}


class FakeEncoder(Encoder):
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


def _matcher(threshold: float = 0.9) -> EmbeddingMatcher:
    return EmbeddingMatcher(FakeEncoder(_VECTORS), threshold=threshold)


def test_matches_when_cosine_similarity_meets_threshold() -> None:
    result = _matcher().match("Coumarinn", "Coumarin")
    assert result is not None
    assert result.method == "embedding"
    assert result.forbidden_ingredient == "Coumarin"
    assert result.matched_text == "Coumarinn"
    assert result.confidence == 1.0


def test_no_match_below_threshold() -> None:
    assert _matcher().match("Water", "Triclosan") is None


def test_custom_threshold_is_respected() -> None:
    strict = EmbeddingMatcher(FakeEncoder(_VECTORS), threshold=0.9)
    assert strict.match("Glucose", "D-Glucopyranose") is None

    lenient = EmbeddingMatcher(FakeEncoder(_VECTORS), threshold=0.5)
    result = lenient.match("Glucose", "D-Glucopyranose")
    assert result is not None
    assert result.confidence == 0.6


def test_formula_shaped_ingredient_is_never_embedded() -> None:
    # Tier 2 owns formula comparisons exhaustively; tier 5 must defer to it
    # rather than risk a false positive from character-overlap-driven
    # similarity between formula strings (see module docstring).
    vectors = {"c6h6": [1.0, 0.0], "coumarin": [1.0, 0.0]}
    matcher = EmbeddingMatcher(FakeEncoder(vectors), threshold=0.5)
    assert matcher.match("C6H6", "Coumarin") is None


def test_empty_normalized_text_does_not_match() -> None:
    vectors = {"": [0.0, 0.0], "coumarin": [1.0, 0.0]}
    matcher = EmbeddingMatcher(FakeEncoder(vectors), threshold=0.1)
    assert matcher.match("---", "Coumarin") is None


def test_embeddings_are_cached_per_text() -> None:
    calls: list[list[str]] = []

    class CountingEncoder(Encoder):
        def encode(self, texts: list[str]) -> list[list[float]]:
            calls.append(list(texts))
            return [_VECTORS[t] for t in texts]

    matcher = EmbeddingMatcher(CountingEncoder(), threshold=0.9)
    matcher.match("Coumarinn", "Coumarin")
    matcher.match("Coumarinn", "Coumarin")

    # Each distinct normalized text should only ever be sent to the encoder once.
    encoded_texts = [text for call in calls for text in call]
    assert encoded_texts.count("coumarinn") == 1
    assert encoded_texts.count("coumarin") == 1
