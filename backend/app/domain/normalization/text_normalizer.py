"""Generic text normalization for tier-1 exact-match comparison.

Unicode-normalizes, casefolds, and strips every non-word character
(punctuation *and* whitespace) so that differences in case, punctuation,
spacing, and bullet formatting never prevent an otherwise-identical
ingredient name from matching, as long as both sides of a comparison are
normalized the same way.
"""

import re
import unicodedata

_NON_WORD_RE = re.compile(r"[^\w]", re.UNICODE)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.casefold()
    return _NON_WORD_RE.sub("", normalized)
