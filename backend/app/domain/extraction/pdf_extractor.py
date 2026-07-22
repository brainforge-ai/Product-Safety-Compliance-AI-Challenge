"""PDF text extraction via PyMuPDF, with a page-rasterization + OCR fallback
for PDFs that turn out to be scans (no embedded text layer).
"""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.core.exceptions import ExtractionError

# Rasterization resolution for the OCR fallback: higher than the PDF's default
# 72 DPI so small label text stays legible after rasterization.
_OCR_ZOOM = 2.0

OcrFunc = Callable[[Image.Image], str]


def _default_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image)


class PdfExtractor:
    def __init__(self, ocr_func: OcrFunc = _default_ocr) -> None:
        self._ocr_func = ocr_func

    def extract(self, path: Path) -> str:
        try:
            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
                if text.strip():
                    return text
                return self._ocr_fallback(doc)
        except RuntimeError as exc:
            raise ExtractionError(f"Could not parse PDF file: {path}") from exc

    def _ocr_fallback(self, doc: fitz.Document) -> str:
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
