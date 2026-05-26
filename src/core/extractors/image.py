"""
Image file extractor using GPT-4o Vision.

Handles .png, .jpg, .jpeg, .gif, .webp files.
"""
from __future__ import annotations
import logging
from pathlib import Path

from src.core.extractors.base import encode_image_file, extract_with_vision
from src.core.models import ProductExtraction

logger = logging.getLogger(__name__)


async def extract_image_file(path: str | Path) -> ProductExtraction:
    """
    Extract product information from an image file using GPT-4o Vision.

    Args:
        path: Path to the image file

    Returns:
        ProductExtraction with extracted data
    """
    path = Path(path)
    logger.info(f"Extracting from image: {path.name}")

    # Encode image to base64
    image_data, media_type = encode_image_file(path)

    # Extract using GPT-4o Vision
    return await extract_with_vision(
        image_base64=image_data,
        media_type=media_type,
        extraction_method="image_vision"
    )
