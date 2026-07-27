"""OCR extraction for image labels (requires Tesseract system binary)."""

from pathlib import Path

import pytesseract
from PIL import Image

from app.core.exceptions import ExtractionError
from app.domain.extraction.base import Extractor


class ImageExtractor(Extractor):
    def extract(self, path: Path) -> str:
        """OCR an image file into plain text."""
        try:
            with Image.open(path) as image:
                return pytesseract.image_to_string(image)
        except pytesseract.TesseractNotFoundError as exc:
            raise ExtractionError(
                "Tesseract OCR binary not found. Install it with "
                "`brew install tesseract` (macOS) or `apt-get install "
                "tesseract-ocr` (Linux), then retry."
            ) from exc
        except OSError as exc:
            raise ExtractionError(f"Could not read image file: {path}") from exc
