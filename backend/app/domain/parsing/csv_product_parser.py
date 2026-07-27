"""Maps a CSV row dict to ExtractedProduct."""

import re

from app.domain.models import ExtractedProduct

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "product_id": ("product_id", "product id", "id"),
    "product_name": ("product_name", "product name", "name"),
    "sku": ("sku",),
    "description": ("description",),
    "ingredients": (
        "ingredients",
        "ingredients / chemical formulas",
        "ingredients/chemical formulas",
        "ingredients_chemical_formulas",
    ),
}

_INGREDIENT_SPLIT_RE = re.compile(r"[;|]")

_DEFAULT_PRODUCT_NAME = "Unknown Product"


def parse_csv_row(row: dict[str, str]) -> ExtractedProduct:
    """Parse one CSV row (as produced by CsvExtractor) into an ExtractedProduct."""
    normalized_row = {_normalize_key(key): value for key, value in row.items()}

    product_id = _lookup(normalized_row, "product_id")
    product_name = _lookup(normalized_row, "product_name") or _DEFAULT_PRODUCT_NAME
    sku = _lookup(normalized_row, "sku")
    description = _lookup(normalized_row, "description")
    ingredients = _split_ingredients(_lookup(normalized_row, "ingredients"))

    return ExtractedProduct(
        product_id=product_id,
        product_name=product_name,
        sku=sku,
        description=description,
        ingredients=ingredients,
        needs_llm_fallback=not ingredients,
    )


def _normalize_key(key: str) -> str:
    """Normalize a CSV header for case- and whitespace-insensitive lookup."""
    return re.sub(r"[\s_]+", " ", key.strip().lower())


def _lookup(normalized_row: dict[str, str], field: str) -> str | None:
    """Return the first non-empty alias value for a logical product field."""
    for alias in _FIELD_ALIASES[field]:
        alias_normalized = _normalize_key(alias)
        if alias_normalized in normalized_row:
            value = normalized_row[alias_normalized].strip()
            if value:
                return value
    return None


def _split_ingredients(raw: str | None) -> list[str]:
    """Split a delimited ingredients cell.

    Deliberately splits on ';' and '|' only, not ',': several forbidden
    ingredients (e.g. "1,4-Dioxane") contain a literal comma, so treating
    comma as a delimiter would corrupt them. Known limitation: a comma-
    delimited ingredients column is not supported.
    """
    if not raw:
        return []
    return [part.strip() for part in _INGREDIENT_SPLIT_RE.split(raw) if part.strip()]
