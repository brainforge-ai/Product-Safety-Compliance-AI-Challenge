"""Lazy-loaded `sentence-transformers` encoder backing tier 5
(ARCHITECTURE.md Section 6).

`sentence-transformers` (and its torch dependency) is imported only inside
`_load_model`, never at module import time, so the app boots and `pytest`
passes fully offline even when the package isn't installed at all (it lives
in the optional `requirements-ai.txt`, not the base `requirements.txt`). The
model itself is loaded once and cached (`functools.lru_cache`), matching the
"lazy singleton at startup" requirement: `main.py` calls `warm_up()` during
the lifespan hook only when `ENABLE_EMBEDDING_MATCHING` is set, so the first
real request never pays the load cost, and the model is never touched at all
when the flag is off.
"""

from functools import lru_cache

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def _load_model(model_name: str = DEFAULT_MODEL_NAME):
    from sentence_transformers import SentenceTransformer  # local import: optional heavy dep

    return SentenceTransformer(model_name)


def encode(texts: list[str], *, model_name: str = DEFAULT_MODEL_NAME) -> list[list[float]]:
    model = _load_model(model_name)
    return model.encode(list(texts)).tolist()


def warm_up(model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Force the lazy singleton to load now, so the first evaluation request
    doesn't pay the model-load cost.
    """
    _load_model(model_name)
