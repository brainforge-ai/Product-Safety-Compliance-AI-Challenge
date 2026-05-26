"""
Base extraction utilities and GPT-4o Vision integration.
"""
from __future__ import annotations
import base64
import logging
from pathlib import Path

from src.core.models import ProductExtraction
from src.core.openai_client import get_openai_client, parse_json_response

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are extracting product information from a product label image.

CRITICAL: The ingredients section may be labeled as any of:
- "Ingredients"
- "Ingredients / Chemical Formulas"
- "INCI"
- "Active Ingredients"
- "Composition"
- "Contains"
- Or NO header at all - just a list of chemicals

Extract the following information:
1. Product ID (format: P-XXXX-XXXX or similar)
2. Product Name
3. SKU (if present)
4. ALL chemical substances/ingredients mentioned, including:
   - Common names (e.g., "Benzene", "Sodium Benzoate", "Hydrogen Peroxide")
   - Chemical formulas (e.g., "C6H6", "H2O2", "C8H10N4O2")
   - IUPAC names
   - Trade names
   - Preserve EXACTLY as written (do not convert formulas to names or vice versa)

Do NOT filter or interpret ingredients. Extract EVERY substance name verbatim.

Return ONLY valid JSON in this exact format:
{
  "product_id": "P-2025-0001",
  "product_name": "Product Name Here",
  "sku": "ABC123",
  "ingredients": ["Ingredient 1", "C6H6", "Ingredient 3"]
}

If a field is not found, use null for product_id/sku, "Unknown" for product_name, and [] for ingredients."""


async def extract_with_vision(
    image_base64: str,
    media_type: str = "image/png",
    extraction_method: str = "image_vision"
) -> ProductExtraction:
    """
    Extract product information from an image using GPT-4o Vision.
    """
    client = get_openai_client()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0,
        )

        content = response.choices[0].message.content
        data = parse_json_response(content)

        if not data:
            data = {"product_name": "Unknown", "ingredients": []}

        return ProductExtraction(
            product_id=data.get("product_id"),
            product_name=data.get("product_name", "Unknown"),
            sku=data.get("sku"),
            ingredients=data.get("ingredients", []),
            extraction_method=extraction_method,
            raw_text=content,
        )

    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        raise


def encode_image_file(path: Path) -> tuple[str, str]:
    """Read and base64 encode an image file."""
    suffix = path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")

    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    return data, media_type
