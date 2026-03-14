"""Parse raw extracted text into structured product data and ingredient lists.

This module is format-agnostic: it handles bullet-point lists, numbered lists,
comma-separated ingredients, table-style CSV data, and Claude Vision's
structured output format.

NOTE: The _CHEM_PREFIXES and _CHEM_SUFFIXES sets below are NOT a forbidden
ingredient list.  They are common chemical name fragments used solely to
rejoin OCR-fragmented ingredient names (e.g. "Propyl" + "Paraben" on
separate lines -> "Propyl Paraben").  Matching is handled entirely by
the matching_engine module using the dynamically loaded forbidden CSV.
"""

import re
from typing import List, Tuple


def parse_ingredients(raw_text: str) -> Tuple[str, str, List[str]]:
    """Parse raw extracted text into (product_id, product_name, ingredients)."""
    product_id = ""
    product_name = ""
    ingredients: List[str] = []

    lines = raw_text.strip().split("\n")
    in_ingredients = False

    for line in lines:
        stripped = _strip_markdown(line.strip())
        if not stripped:
            continue

        lower = stripped.lower()

        if _matches_field(lower, "product id"):
            product_id = _extract_value(stripped)
            continue

        if _matches_field(lower, "product name"):
            product_name = _extract_value(stripped)
            continue

        if _is_ingredient_header(lower):
            in_ingredients = True
            after = stripped.split(":", 1)
            if len(after) > 1 and after[1].strip():
                _add_ingredients(after[1].strip(), ingredients)
            continue

        if stripped.startswith("--") and stripped.endswith("--"):
            in_ingredients = False
            continue

        if lower.startswith("readability:"):
            continue

        if in_ingredients:
            cleaned = _strip_bullet(stripped)
            if cleaned and len(cleaned) > 1:
                _add_ingredients(cleaned, ingredients)

    ingredients = _rejoin_fragments(ingredients)
    return product_id, product_name, ingredients


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_markdown(text: str) -> str:
    text = text.replace("**", "")
    text = text.replace("__", "")
    return text.strip()


def _matches_field(lower_line: str, field: str) -> bool:
    return lower_line.startswith(field) and ":" in lower_line


def _extract_value(line: str) -> str:
    return line.split(":", 1)[1].strip()


def _is_ingredient_header(lower_line: str) -> bool:
    keywords = ["ingredient", "chemical formula", "composition", "active compound"]
    return any(kw in lower_line for kw in keywords)


def _strip_bullet(text: str) -> str:
    text = re.sub(r"^[\-\*\u2022\u00b7\u25aa\u25ba]\s*", "", text)
    text = re.sub(r"^\d+[\.\)]\s*", "", text)
    return text.strip()


_CHEM_FORMULA_RE = re.compile(
    r"^[A-Z][a-z]?\d*"          # starts with element symbol
    r"(\([A-Z][a-z0-9A-Z]*\)"   # parenthesized group like (OH), (C2H3O2)
    r"\d*)+$"                    # optional subscript after closing paren
)


def _is_chemical_formula(text: str) -> bool:
    """Return True if the text looks like a chemical formula with parentheses."""
    stripped = text.strip()
    if not stripped:
        return False
    if _CHEM_FORMULA_RE.match(stripped):
        return True
    if re.match(r"^[A-Z][a-z]?\d*\(", stripped) and stripped[-1].isdigit():
        return True
    return False


def _add_ingredients(text: str, ingredients: List[str]) -> None:
    """Split text into individual ingredients and add them to the list.

    Handles:
    - Chemical formulas with parentheses: "Pb(C2H3O2)2" stays intact
    - Parenthetical translations: "text (English name)" -> adds both
    - Chemical formulas with commas: "1,4-Dioxane" stays intact
    - Comma-separated lists: "A, B, C" -> ["A", "B", "C"]
    """
    if _is_chemical_formula(text):
        ingredients.append(text.strip())
        return

    paren_match = re.search(r"\(([A-Za-z][A-Za-z0-9\s\-,]+)\)", text)
    if paren_match:
        english_name = paren_match.group(1).strip()
        if english_name and len(english_name) > 2:
            ingredients.append(english_name)
        outside = re.sub(r"\([^)]*\)", "", text).strip()
        if outside and len(outside) > 1:
            ingredients.append(outside)
        return

    if "|" in text:
        for item in text.split("|"):
            item = item.strip()
            if item:
                _add_ingredients(item, ingredients)
        return

    if re.match(r"^\d+,\d+", text):
        ingredients.append(text.strip())
        return

    if "," not in text or re.match(r"^[A-Z][a-z]*\d", text):
        ingredients.append(text.strip())
        return

    for item in text.split(","):
        item = item.strip()
        if item:
            _add_ingredients(item, ingredients)


# ---------------------------------------------------------------------------
# OCR fragment rejoining
#
# These sets help recombine ingredient names that OCR split across lines.
# They are NOT forbidden ingredients -- they are common chemical name parts.
# ---------------------------------------------------------------------------

_CHEM_SUFFIXES = {
    "paraben", "sulfate", "sulfite", "benzoate", "hydroxide", "carbonate",
    "chloride", "oxide", "acid", "glycol", "alcohol", "amine", "dioxane",
    "betaine", "palmitate", "sorbate", "stearate", "citrate",
}
_CHEM_PREFIXES = {
    "sodium", "methyl", "ethyl", "propyl", "butyl", "potassium", "calcium",
    "butylated", "diethylene", "cocamidopropyl", "retinyl",
}


def _rejoin_fragments(ingredients: List[str]) -> List[str]:
    """Rejoin ingredient name fragments split across lines by OCR.

    E.g. ["Propyl", "Paraben"] -> ["Propyl Paraben"]
         ["Sodium", "Lauryl", "Sulfate"] -> ["Sodium Lauryl Sulfate"]
    """
    if len(ingredients) < 2:
        return ingredients

    result: List[str] = []
    i = 0
    while i < len(ingredients):
        current = ingredients[i].strip()
        current_lower = current.lower()

        if current_lower in _CHEM_PREFIXES and i + 1 < len(ingredients):
            combined = current
            j = i + 1
            while j < len(ingredients) and j <= i + 2:
                next_item = ingredients[j].strip()
                combined = combined + " " + next_item
                j += 1
                if next_item.lower() in _CHEM_SUFFIXES:
                    break
            result.append(combined)
            i = j
            continue

        if current_lower in _CHEM_SUFFIXES and result:
            prev = result[-1].lower()
            if prev in _CHEM_PREFIXES or any(prev.endswith(p) for p in _CHEM_PREFIXES):
                result[-1] = result[-1] + " " + current
                i += 1
                continue

        result.append(current)
        i += 1

    return result
