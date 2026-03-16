"""Ingredient parsing utilities."""

import re

from ..extraction.normalizer import cleanup_ocr_artifacts


FORMULA_TOKEN_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+$")


def _repair_formula_ocr_token(token: str) -> str:
    """Repair common OCR damage in chemical-formula-like tokens."""
    value = cleanup_ocr_artifacts(token, lowercase=False)
    if not value:
        return ""

    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if not compact:
        return ""

    # Generic OCR repairs observed in formula tokens.
    compact = compact.replace("ION", "10N")
    compact = compact.replace("0O", "O2").replace("OO", "O2")
    compact = re.sub(r"(?<=[A-Z])(I|L)(?=\d)", "1", compact)
    compact = re.sub(r"(?<=\d)(I|L)(?=[A-Z])", "1", compact)

    if FORMULA_TOKEN_PATTERN.match(compact):
        return compact
    return value


def _normalize_ingredient_token(token: str) -> str:
    """Normalize extracted ingredient tokens while preserving formulas."""
    item = cleanup_ocr_artifacts(token, lowercase=False).strip()
    item = re.sub(r"^\[|\]$", "", item).strip()
    if not item:
        return ""
    repaired = _repair_formula_ocr_token(item)
    if FORMULA_TOKEN_PATTERN.match(re.sub(r"[^A-Za-z0-9]", "", repaired)):
        return re.sub(r"[^A-Za-z0-9]", "", repaired).upper()
    return item.strip()


def extract_product_name(text):
    """
    Extract the product name from free-form text.

    Looks for patterns like "Product Name:", "Product:", "Name:", etc.
    For OCR/image text, falls back to the first substantial line.
    """
    if not (text and text.strip()):
        return "Unknown Product"

    text_lower = text.lower().strip()
    patterns = [
        r"product name[: ]*([^\n]+)",
        r"product[: ]*([^\n]+)",
        r"^name[: ]*([^\n]+)",
        r"item[: ]*([^\n]+)",
        r"^([^\n]{3,60})$",  # Single line (e.g. from OCR) as product name
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if name and len(name) > 2 and not name.startswith("ingredient"):
                return name.title()

    # Fallback: first non-empty line that looks like a title (not a list header)
    for line in text.strip().splitlines():
        line = line.strip()
        if len(line) >= 3 and len(line) <= 80 and line.lower() not in ("ingredients", "composition", "warnings"):
            return line.title()

    return "Unknown Product"


def extract_ingredients(text):
    """
    Extract an ingredient list from free-form text.

    Handles:
    - Single-line:  "Ingredients: a, b, c"
    - Multi-line ingredient blocks
    - Semicolon-separated lists
    - Chemical names like 1,4-Dihydroxybenzene
    """

    source_text = cleanup_ocr_artifacts(text or "", lowercase=False, preserve_newlines=True)
    text_lower = source_text.lower()
    # Match common section headers (including OCR-style with line break after)
    pattern = (
        r"(?:ingredients?|composition|contents|formula|components?)[: ]*(.+?)(?:\n\s*\n|warnings?:|usage instructions?:|directions?:|allergen|may contain|product name[: ]|product[: ]|name[: ]|$)"
    )
    match = re.search(pattern, source_text, flags=re.DOTALL | re.IGNORECASE)

    if not match:
        # Fallback: "Contains: X _ Y" or "Contains: X, Y" style (common in OCR labels)
        contains_match = re.search(
            r"contains?[:\s]+(.+?)(?:\n\n|$)",
            text_lower,
            re.DOTALL | re.IGNORECASE,
        )
        if contains_match:
            block = contains_match.group(1).strip()
        elif text_lower.strip() and len(text_lower.strip()) <= 1200 and ("," in text_lower or "\n" in text_lower or "_" in text_lower):
            block = source_text.strip()
        else:
            return []
    else:
        block = match.group(1)

    # Protect chemical commas like 1,4-Dihydroxybenzene before splitting
    block = re.sub(r"(\d),(\d)", r"\1§\2", block)
    block = block.replace(";", ",")

    # Split by explicit ingredient separators while preserving multi-word ingredient names.
    # This keeps phrases like "sodium lauryl sulfate" intact instead of breaking them into words.
    raw_items = re.split(r"[,\n_;|]+", block)

    ingredients = []
    for item in raw_items:
        item = item.replace("§", ",").strip()
        normalized_item = _normalize_ingredient_token(item)
        if len(normalized_item) > 0 and normalized_item.lower() not in ("and", "&", ""):
            ingredients.append(normalized_item)

    # Merge "X" + "Acid" into "X Acid" when adjacent (generic rule; no hardcoded ingredient names).
    merged = []
    i = 0
    while i < len(ingredients):
        if i + 1 < len(ingredients) and ingredients[i + 1].strip().lower() == "acid":
            merged.append(ingredients[i] + " " + ingredients[i + 1])
            i += 2
        else:
            merged.append(ingredients[i])
            i += 1

    return merged