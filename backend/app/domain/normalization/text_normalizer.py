"""Text normalization for exact-match comparison (case, punctuation, whitespace)."""

import re
import unicodedata
from functools import lru_cache

_NON_WORD_RE = re.compile(r"[^\w]", re.UNICODE)


@lru_cache(maxsize=8192)
def normalize_text(text: str) -> str:
    """Normalize text for case- and punctuation-insensitive comparison."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.casefold()
    return _NON_WORD_RE.sub("", normalized)
