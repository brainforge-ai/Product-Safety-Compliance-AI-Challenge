"""Molecular formula canonicalization: parse a flat chemical formula string
(e.g. `C6H6`, `H2O2`) into an order-independent `{element: count}` dict.

Known limitation: only simple flat formulas are supported (no nested
parentheses, no hydrate notation like `CuSO4.5H2O`); this matches the
dataset and keeps the parser honest rather than over-engineered.

This parser is deliberately strict and makes no attempt to correct OCR
misreadings (e.g. `H2O2` scanned as `H202`, or a leading `C` scanned as
`€`). Context-free, such corruption is genuinely ambiguous — `H202` could
be `H:202` or `H:2, O:2`, and nothing in the string alone decides which.
That correction is resolved in the Phase 5 formula matcher instead, where
it can be checked against a specific forbidden-list formula (the forbidden
entry acts as the oracle that disambiguates a candidate correction).
"""

import re

from app.domain.normalization.elements import ELEMENT_SYMBOLS

_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
_UNSUPPORTED_CHARS_RE = re.compile(r"[\s().]")


def parse_formula(text: str) -> dict[str, int] | None:
    """Strictly parse a flat molecular formula string.

    Returns None if the text contains unsupported syntax (whitespace,
    parentheses, hydrate dots) or any token that isn't a recognized element
    symbol, or if the string isn't fully consumed by element/count tokens.
    """
    candidate = text.strip()
    if not candidate or _UNSUPPORTED_CHARS_RE.search(candidate):
        return None

    counts: dict[str, int] = {}
    pos = 0
    while pos < len(candidate):
        match = _TOKEN_RE.match(candidate, pos)
        if not match or not match.group(1):
            return None
        element, count_str = match.groups()
        if element not in ELEMENT_SYMBOLS:
            return None
        counts[element] = counts.get(element, 0) + (int(count_str) if count_str else 1)
        pos = match.end()

    return counts or None


def is_formula(text: str) -> bool:
    """Heuristic: does this text look like a (possibly OCR-corrupted) flat
    molecular formula, as opposed to an ingredient name?

    Deliberately permissive rather than chemically strict: a corrupted
    formula like `H202` still parses successfully here (as `H:202`), which
    is intentional so it routes into the formula-matching tier rather than
    being treated as a plain name.
    """
    return parse_formula(text) is not None


def formulas_equal(a: str, b: str) -> bool:
    """Order-independent equality between two formula strings, e.g. `H2O2`
    equals `O2H2`. Returns False if either side doesn't parse as a formula.
    """
    parsed_a = parse_formula(a)
    if parsed_a is None:
        return False
    return parsed_a == parse_formula(b)
