from pathlib import Path

import fitz
import pytest

from app.core.exceptions import ExtractionError
from app.domain.extraction.pdf_extractor import PdfExtractor


def test_extracts_text_from_real_samples(fixtures_dir: Path) -> None:
    extractor = PdfExtractor()
    sample_files = sorted((fixtures_dir / "pdfs").glob("*.pdf"))
    assert len(sample_files) == 10

    for path in sample_files:
        text = extractor.extract(path)
        assert "Product ID" in text
        assert "Ingredients" in text


def test_falls_back_to_ocr_when_text_layer_is_empty(tmp_path: Path) -> None:
    # Build a PDF with no embedded text layer: a page containing only a
    # rasterized image of text, forcing the OCR fallback path.
    source_doc = fitz.open()
    page = source_doc.new_page()
    page.insert_text(
        (72, 72), "Product ID: P-2025-9999\nIngredients / Chemical Formulas:\n- Coumarin"
    )
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    image_bytes = pixmap.tobytes("png")
    source_doc.close()

    image_only_doc = fitz.open()
    image_page = image_only_doc.new_page()
    image_page.insert_image(image_page.rect, stream=image_bytes)
    pdf_path = tmp_path / "scanned.pdf"
    image_only_doc.save(pdf_path)
    image_only_doc.close()

    extractor = PdfExtractor()
    text = extractor.extract(pdf_path)

    assert "Coumarin" in text


def test_corrupt_pdf_raises_extraction_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a real pdf")

    with pytest.raises(ExtractionError):
        PdfExtractor().extract(path)


def test_missing_pdf_raises_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError):
        PdfExtractor().extract(tmp_path / "missing.pdf")


def test_ocr_fallback_uses_injected_ocr_func(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    # A blank page (no text layer, no readable image) still exercises the
    # fallback path deterministically via a stubbed OCR function.
    page.insert_image(page.rect, stream=_blank_png())
    pdf_path = tmp_path / "blank.pdf"
    doc.save(pdf_path)
    doc.close()

    calls: list[object] = []

    def fake_ocr(image: object) -> str:
        calls.append(image)
        return "stubbed ocr text"

    extractor = PdfExtractor(ocr_func=fake_ocr)
    text = extractor.extract(pdf_path)

    assert text == "stubbed ocr text"
    assert len(calls) == 1


def _blank_png() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    pixmap = page.get_pixmap()
    png_bytes = pixmap.tobytes("png")
    doc.close()
    return png_bytes
