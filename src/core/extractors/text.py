"""
Text file extractor for structured product data.

Handles .txt files with format:
    Product ID: P-2025-0001
    Product Name: Product Name
    SKU: ABC123
    ...
    Ingredients / Chemical Formulas:
    - Ingredient 1
    - Ingredient 2
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

from src.core.models import ProductExtraction

logger = logging.getLogger(__name__)


async def extract_text_file(path: str | Path) -> ProductExtraction:
    """
    Extract product information from a structured text file.

    Args:
        path: Path to the .txt file

    Returns:
        ProductExtraction with parsed data
    """
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_text_content(content)


def parse_text_content(content: str) -> ProductExtraction:
    """
    Parse product data from text content.

    Handles various section headers and formats.
    """
    lines = content.strip().split("\n")

    product_id = None
    product_name = "Unknown"
    sku = None
    ingredients: list[str] = []

    in_ingredients_section = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for key-value pairs
        if ":" in line and not in_ingredients_section:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if "product id" in key:
                product_id = value
            elif "product name" in key:
                product_name = value
            elif "sku" in key:
                sku = value
            elif any(x in key for x in ["ingredient", "formula", "inci", "composition", "contains"]):
                in_ingredients_section = True
                # Check if there's a value on the same line
                if value and not value.startswith("-"):
                    ingredients.extend(_parse_ingredient_line(value))

        elif in_ingredients_section:
            # Parse ingredient line
            ingredients.extend(_parse_ingredient_line(line))

    # Deduplicate while preserving order
    seen = set()
    unique_ingredients = []
    for ing in ingredients:
        if ing.lower() not in seen:
            seen.add(ing.lower())
            unique_ingredients.append(ing)

    return ProductExtraction(
        product_id=product_id,
        product_name=product_name,
        sku=sku,
        ingredients=unique_ingredients,
        extraction_method="text",
        raw_text=content,
    )


def _parse_ingredient_line(line: str) -> list[str]:
    """
    Parse ingredients from a single line.

    Handles:
    - "- Ingredient 1"
    - "Ingredient 1, Ingredient 2, Ingredient 3"
    - "* Ingredient 1"
    - "1. Ingredient 1"
    """
    # Remove common list prefixes
    line = re.sub(r"^[-*•]\s*", "", line)
    line = re.sub(r"^\d+\.\s*", "", line)
    line = line.strip()

    if not line:
        return []

    # Check if comma-separated (but be careful with "1,4-Dioxane")
    # Only split on comma if followed by space and then a letter
    if re.search(r",\s+[A-Za-z]", line):
        # Split on ", " but preserve things like "1,4-Dioxane"
        parts = re.split(r",\s+(?=[A-Za-z])", line)
        return [p.strip() for p in parts if p.strip()]

    return [line] if line else []
