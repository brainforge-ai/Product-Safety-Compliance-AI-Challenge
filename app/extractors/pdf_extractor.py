"""Extract text from PDFs using PyMuPDF, with per-page Claude Vision fallback.

Strategy:
- Each page is individually checked for extractable text via PyMuPDF.
- If a page yields fewer than MIN_PAGE_TEXT characters, it is treated as
  scanned/image-based and rendered at 300 DPI for Claude Vision OCR.
- This handles mixed PDFs where some pages are digital text and others
  are scanned images or photos.
"""

import os
import tempfile
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Per-page threshold: below this, the page is likely scanned/image-only.
MIN_PAGE_TEXT = 20


def extract_from_pdf(file_path: str) -> str:
    """Extract text from a PDF with per-page digital/scanned detection.

    For each page:
      - Try PyMuPDF text extraction first (free, instant, exact).
      - If the page has too little text (likely scanned), render it
        as a 300 DPI image and run Claude Vision OCR.
    """
    from app.extractors.image_extractor import extract_from_image

    doc = fitz.open(file_path)
    page_texts = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()

        if len(text) >= MIN_PAGE_TEXT:
            # Digital page -- PyMuPDF extracted real text
            logger.info("PDF page %d: digital text (%d chars)", i + 1, len(text))
            page_texts.append(text)
        else:
            # Scanned/image page -- fall back to Claude Vision OCR
            logger.info("PDF page %d: scanned/image, running OCR", i + 1)
            page_texts.append(_ocr_page(page))

    doc.close()
    return "\n".join(page_texts)


def _ocr_page(page) -> str:
    """Render a single PDF page as a 300 DPI image and run Claude Vision OCR."""
    from app.extractors.image_extractor import extract_from_image

    pix = page.get_pixmap(dpi=300)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    pix.save(tmp.name)
    tmp.close()
    try:
        return extract_from_image(tmp.name)
    finally:
        os.unlink(tmp.name)
