"""Lazy-loaded sentence-transformers encoder for tier 5."""

from functools import lru_cache

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _load_model(model_name: str = DEFAULT_MODEL_NAME):
    """Load and cache the sentence-transformers model singleton."""
    from sentence_transformers import SentenceTransformer  # local import: optional heavy dep

    return SentenceTransformer(model_name)


def encode(texts: list[str], *, model_name: str = DEFAULT_MODEL_NAME) -> list[list[float]]:
    """Encode texts into embedding vectors using the lazy-loaded model."""
    model = _load_model(model_name)
    return model.encode(list(texts)).tolist()


def warm_up(model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Force the lazy singleton to load now, so the first evaluation request
    doesn't pay the model-load cost.
    """
    _load_model(model_name)
