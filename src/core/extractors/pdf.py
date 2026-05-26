"""
PDF file extractor using pdf2image + GPT-4o Vision.

Uses a single code path for ALL PDFs (both generated and scanned):
1. Convert PDF page to image using pdf2image
2. Send image to GPT-4o Vision for extraction

This avoids the complexity of detecting PDF type and handles all cases.
"""
from __future__ import annotations
import base64
import io
import logging
from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image

from src.core.extractors.base import extract_with_vision
from src.core.models import ProductExtraction

logger = logging.getLogger(__name__)


async def extract_pdf_file(path: str | Path, dpi: int = 200) -> ProductExtraction:
    """
    Extract product information from a PDF file.

    Converts PDF to image and uses GPT-4o Vision for extraction.
    This single code path handles both machine-readable and scanned PDFs.

    Args:
        path: Path to the PDF file
        dpi: Resolution for PDF rendering (higher = better quality but slower)

    Returns:
        ProductExtraction with extracted data
    """
    path = Path(path)
    logger.info(f"Extracting from PDF: {path.name}")

    try:
        # Convert PDF to images (one per page)
        images = convert_from_path(path, dpi=dpi)

        if not images:
            logger.warning(f"No pages found in PDF: {path}")
            return ProductExtraction(
                product_name="Unknown",
                ingredients=[],
                extraction_method="pdf_vision",
            )

        # Use first page (product labels are typically single-page)
        image = images[0]

        # Convert PIL Image to base64
        image_data = _pil_to_base64(image)

        # Extract using GPT-4o Vision
        return await extract_with_vision(
            image_base64=image_data,
            media_type="image/png",
            extraction_method="pdf_vision"
        )

    except Exception as e:
        logger.error(f"PDF extraction failed for {path}: {e}")
        raise


def _pil_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
