"""OCR-based extraction for image product labels (pytesseract + Pillow).

Requires the Tesseract system binary (`brew install tesseract` /
`apt-get install tesseract-ocr`); a missing binary is surfaced as a clear,
actionable ExtractionError rather than a silent failure.
"""

from pathlib import Path

import pytesseract
from PIL import Image

from app.core.exceptions import ExtractionError


class ImageExtractor:
    def extract(self, path: Path) -> str:
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
