"""Regex/heuristic parser for structured product fields from a text blob."""

import re

from app.domain.models import ExtractedProduct

_PRODUCT_ID_RE = re.compile(r"Product\s*ID\s*:\s*(.+)", re.IGNORECASE)
_PRODUCT_NAME_RE = re.compile(r"Product\s*Name\s*:\s*(.+)", re.IGNORECASE)
_SKU_RE = re.compile(r"SKU\s*:\s*(.+)", re.IGNORECASE)
_DESCRIPTION_RE = re.compile(
    r"Description\s*:\s*\n(.+?)(?=\n\s*Ingredients|\Z)", re.IGNORECASE | re.DOTALL
)
_INGREDIENTS_HEADER_RE = re.compile(
    r"^\s*(?:ingredients?(?:\s*/\s*chemical\s*formulas?)?|"
    r"ingredient\s+list|composition)\s*:\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Product labels commonly put one of these sections after ingredients. Do not
# accidentally treat warnings or directions as ingredients just because they
# occur later in the extracted text.
_END_SECTION_RE = re.compile(
    r"^\s*(?:warnings?|cautions?|directions?|instructions?|usage|storage|"
    r"manufacturer|manufactured\s+by|distributed\s+by|net\s+(?:weight|wt)|"
    r"claims?)\s*:",
    re.IGNORECASE,
)

# Strip a single leading bullet marker: either symbolic bullet characters, or
# a numbered-list marker (digits followed by '.'/')' and whitespace). The
# numbered-list branch requires trailing whitespace so it never consumes a
# digit that is actually part of the ingredient text itself (e.g. the
# forbidden ingredient "1,4-Dioxane" must not be mistaken for a "1." marker).
_BULLET_RE = re.compile(r"^\s*(?:[-*•‣◦⁃∙]+\s*|\d+[.)]\s+)")

_DEFAULT_PRODUCT_NAME = "Unknown Product"


def parse_product_text(text: str) -> ExtractedProduct:
    """Parse structured product fields and ingredients from label text."""
    ingredients = _extract_ingredients(text)

    return ExtractedProduct(
        product_id=_extract_field(_PRODUCT_ID_RE, text),
        product_name=_extract_field(_PRODUCT_NAME_RE, text) or _DEFAULT_PRODUCT_NAME,
        sku=_extract_field(_SKU_RE, text),
        description=_extract_field(_DESCRIPTION_RE, text, join_lines=True),
        ingredients=ingredients,
        needs_llm_fallback=not ingredients,
    )


def _extract_field(pattern: re.Pattern[str], text: str, *, join_lines: bool = False) -> str | None:
    """Extract and clean the first regex capture group from text."""
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1)
    if join_lines:
        value = " ".join(line.strip() for line in value.splitlines() if line.strip())
    return value.strip() or None


def _extract_ingredients(text: str) -> list[str]:
    """Parse inline, delimited, or bullet-listed ingredients.

    The supplied samples use ``Ingredients / Chemical Formulas:``, but real
    labels much more often use ``Ingredients:`` or ``Ingredient List:`` and
    may put the whole list on the same line. Commas followed by whitespace are
    treated as delimiters only outside parentheses, preserving names such as
    ``1,4-Dioxane``.
    """
    header_match = _INGREDIENTS_HEADER_RE.search(text)
    if not header_match:
        return []

    lines = [header_match.group(1), *text[header_match.end() :].splitlines()]
    ingredients: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if _END_SECTION_RE.match(line):
            break
        cleaned = _BULLET_RE.sub("", line).strip()
        if not cleaned:
            continue
        for ingredient in split_ingredient_list(cleaned):
            key = ingredient.casefold()
            if key not in seen:
                seen.add(key)
                ingredients.append(ingredient)
    return ingredients


def split_ingredient_list(raw: str) -> list[str]:
    """Split common ingredient delimiters while respecting bracketed text."""
    parts: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(raw):
        char = raw[index]
        if char in "([":
            depth += 1
        elif char in ")]" and depth:
            depth -= 1

        comma_delimiter = char == "," and index + 1 < len(raw) and raw[index + 1].isspace()
        if depth == 0 and (char in ";|" or comma_delimiter):
            value = raw[start:index].strip()
            if value:
                parts.append(value)
            index += 1
            while index < len(raw) and raw[index].isspace():
                index += 1
            start = index
            continue
        index += 1

    value = raw[start:].strip()
    if value:
        parts.append(value)
    return parts
