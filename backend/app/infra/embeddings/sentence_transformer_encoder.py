"""Lazy-loaded sentence-transformers encoder for tier 5."""

from functools import lru_cache

from app.infra.embeddings.base import Encoder

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _load_model(model_name: str = DEFAULT_MODEL_NAME, *, local_files_only: bool = False):
    """Load and cache the sentence-transformers model singleton."""
    from sentence_transformers import SentenceTransformer  # local import: optional heavy dep

    return SentenceTransformer(model_name, local_files_only=local_files_only)


class SentenceTransformerEncoder(Encoder):
    def __init__(
        self, model_name: str = DEFAULT_MODEL_NAME, *, local_files_only: bool = False
    ) -> None:
        self._model_name = model_name
        self._local_files_only = local_files_only

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into embedding vectors using the lazy-loaded model."""
        model = _load_model(self._model_name, local_files_only=self._local_files_only)
        return model.encode(list(texts)).tolist()


def encode(
    texts: list[str],
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    local_files_only: bool = False,
) -> list[list[float]]:
    """Encode texts into embedding vectors using the lazy-loaded model."""
    return SentenceTransformerEncoder(model_name, local_files_only=local_files_only).encode(texts)


def warm_up(model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Force the lazy singleton to load now, so the first evaluation request
    doesn't pay the model-load cost.
    """
    _load_model(model_name)
