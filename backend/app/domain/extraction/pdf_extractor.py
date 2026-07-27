"""PDF text extraction with OCR fallback for scanned pages."""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.core.exceptions import ExtractionError

# Higher than default 72 DPI so small label text stays legible after rasterization.
_OCR_ZOOM = 2.0

OcrFunc = Callable[[Image.Image], str]


def _default_ocr(image: Image.Image) -> str:
    """Run Tesseract OCR on a rasterized page image."""
    return pytesseract.image_to_string(image)


class PdfExtractor:
    def __init__(self, ocr_func: OcrFunc = _default_ocr) -> None:
        """Configure PDF extraction with a pluggable OCR fallback."""
        self._ocr_func = ocr_func

    def extract(self, path: Path) -> str:
        """Extract text from a PDF, falling back to OCR when pages have no text."""
        try:
            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
                if text.strip():
                    return text
                return self._ocr_fallback(doc)
        except RuntimeError as exc:
            raise ExtractionError(f"Could not parse PDF file: {path}") from exc

    def _ocr_fallback(self, doc: fitz.Document) -> str:
        """OCR every page when the PDF contains no extractable text layer."""
        matrix = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)
        pages_text = []
        try:
            for page in doc:
                pixmap = page.get_pixmap(matrix=matrix)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                pages_text.append(self._ocr_func(image))
        except pytesseract.TesseractNotFoundError as exc:
            raise ExtractionError(
                "Tesseract OCR binary not found. Install it with "
                "`brew install tesseract` (macOS) or `apt-get install "
                "tesseract-ocr` (Linux), then retry."
            ) from exc
        return "\n".join(pages_text)
