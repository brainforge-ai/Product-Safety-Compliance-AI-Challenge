"""Text normalization for exact-match comparison (case, punctuation, whitespace)."""

import re
import unicodedata

_NON_WORD_RE = re.compile(r"[^\w]", re.UNICODE)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.casefold()
    return _NON_WORD_RE.sub("", normalized)
