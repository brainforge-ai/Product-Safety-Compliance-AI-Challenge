"""PDF text extraction with OCR fallback for scanned pages."""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.core.exceptions import ExtractionError
from app.domain.extraction.base import Extractor

# Higher than default 72 DPI so small label text stays legible after rasterization.
_OCR_ZOOM = 2.0
_MAX_PDF_PAGES = 100

OcrFunc = Callable[[Image.Image], str]


def _default_ocr(image: Image.Image) -> str:
    """Run Tesseract OCR on a rasterized page image."""
    return pytesseract.image_to_string(image)


class PdfExtractor(Extractor):
    def __init__(self, ocr_func: OcrFunc = _default_ocr) -> None:
        """Configure PDF extraction with a pluggable OCR fallback."""
        self._ocr_func = ocr_func

    def extract(self, path: Path) -> str:
        """Extract text from each PDF page, OCRing only pages with no text layer."""
        try:
            with fitz.open(path) as doc:
                if doc.page_count > _MAX_PDF_PAGES:
                    raise ExtractionError(
                        f"PDF has {doc.page_count} pages; maximum is {_MAX_PDF_PAGES}."
                    )
                pages_text = []
                for page in doc:
                    text = page.get_text()
                    pages_text.append(text if text.strip() else self._ocr_page(page))
                return "\n".join(pages_text)
        except RuntimeError as exc:
            raise ExtractionError(f"Could not parse PDF file: {path}") from exc

    def _ocr_page(self, page: fitz.Page) -> str:
        """Rasterize and OCR one page with no usable embedded text."""
        # Scale up rasterization so Tesseract sees label-sized text, not tiny glyphs.
        matrix = fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM)
        try:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            return self._ocr_func(image)
        except pytesseract.TesseractNotFoundError as exc:
            raise ExtractionError(
                "Tesseract OCR binary not found. Install it with "
                "`brew install tesseract` (macOS) or `apt-get install "
                "tesseract-ocr` (Linux), then retry."
            ) from exc
