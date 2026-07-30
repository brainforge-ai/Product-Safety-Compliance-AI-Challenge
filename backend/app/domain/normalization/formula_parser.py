"""Parse molecular formulas into order-independent element counts.

Supports flat formulas, grouped formulas such as ``Ca(OH)2``, and hydrate
notation such as ``CuSO4·5H2O``. OCR corruption recovery remains the formula
matcher's responsibility rather than being guessed here.
"""

import re
from functools import lru_cache

from app.domain.normalization.elements import ELEMENT_SYMBOLS

_ELEMENT_RE = re.compile(r"[A-Z][a-z]?")
_COUNT_RE = re.compile(r"\d+")
_UNSUPPORTED_CHARS_RE = re.compile(r"[\s{}]")
_OPEN_TO_CLOSE = {"(": ")", "[": "]"}


class _FormulaParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def parse(self, closing: str | None = None) -> dict[str, int] | None:
        counts: dict[str, int] = {}
        consumed = False

        while self.pos < len(self.text):
            char = self.text[self.pos]
            if closing and char == closing:
                break
            if char in ")]":
                return None

            if char in _OPEN_TO_CLOSE:
                self.pos += 1
                nested = self.parse(_OPEN_TO_CLOSE[char])
                if nested is None or self.pos >= len(self.text):
                    return None
                self.pos += 1  # closing bracket
                multiplier = self._count()
                for element, count in nested.items():
                    counts[element] = counts.get(element, 0) + count * multiplier
                consumed = True
                continue

            match = _ELEMENT_RE.match(self.text, self.pos)
            if match is None or match.group() not in ELEMENT_SYMBOLS:
                return None
            self.pos = match.end()
            element = match.group()
            counts[element] = counts.get(element, 0) + self._count()
            consumed = True

        if closing and (self.pos >= len(self.text) or self.text[self.pos] != closing):
            return None
        return counts if consumed else None

    def _count(self) -> int:
        match = _COUNT_RE.match(self.text, self.pos)
        if match is None:
            return 1
        self.pos = match.end()
        return int(match.group())


def _parse_component(component: str) -> dict[str, int] | None:
    """Parse one side of a hydrate dot, including an optional coefficient."""
    coefficient = 1
    coefficient_match = _COUNT_RE.match(component)
    if coefficient_match:
        coefficient = int(coefficient_match.group())
        component = component[coefficient_match.end() :]
    if not component:
        return None

    parser = _FormulaParser(component)
    counts = parser.parse()
    if counts is None or parser.pos != len(component):
        return None
    return {element: count * coefficient for element, count in counts.items()}


@lru_cache(maxsize=8192)
def _canonical_formula(text: str) -> tuple[tuple[str, int], ...] | None:
    candidate = text.strip()
    if not candidate or _UNSUPPORTED_CHARS_RE.search(candidate):
        return None

    total: dict[str, int] = {}
    for component in re.split(r"[.·]", candidate):
        counts = _parse_component(component)
        if counts is None:
            return None
        for element, count in counts.items():
            total[element] = total.get(element, 0) + count
    return tuple(sorted(total.items())) or None


def parse_formula(text: str) -> dict[str, int] | None:
    """Parse a molecular formula, returning total element counts or ``None``."""
    canonical = _canonical_formula(text)
    return dict(canonical) if canonical is not None else None


def is_formula(text: str) -> bool:
    """Return whether text looks like a formula, including common OCR damage."""
    return (
        _canonical_formula(text) is not None
        or _canonical_formula(text.replace("€", "C")) is not None
    )


def formulas_equal(a: str, b: str) -> bool:
    """Return order-independent molecular-formula equality."""
    parsed_a = _canonical_formula(a)
    return parsed_a is not None and parsed_a == _canonical_formula(b)
