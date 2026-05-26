"""
Extractors package - handles extraction from various file formats.
"""
from __future__ import annotations
import logging
from pathlib import Path

from src.core.models import ProductExtraction
from src.core.extractors.text import extract_text_file
from src.core.extractors.image import extract_image_file
from src.core.extractors.pdf import extract_pdf_file

logger = logging.getLogger(__name__)

# Supported file extensions by type
TEXT_EXTENSIONS = {".txt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}


async def extract_product(path: str | Path) -> ProductExtraction:
    """
    Extract product information from any supported file type.

    Automatically routes to the appropriate extractor based on file extension.

    Args:
        path: Path to the product file

    Returns:
        ProductExtraction with extracted data

    Raises:
        ValueError: If file type is not supported
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        logger.info(f"Using text extractor for: {path.name}")
        return await extract_text_file(path)

    elif suffix in IMAGE_EXTENSIONS:
        logger.info(f"Using image extractor for: {path.name}")
        return await extract_image_file(path)

    elif suffix in PDF_EXTENSIONS:
        logger.info(f"Using PDF extractor for: {path.name}")
        return await extract_pdf_file(path)

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


__all__ = [
    "extract_product",
    "extract_text_file",
    "extract_image_file",
    "extract_pdf_file",
]
