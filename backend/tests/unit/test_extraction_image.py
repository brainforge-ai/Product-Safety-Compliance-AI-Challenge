import re
from pathlib import Path

from app.domain.extraction.image_extractor import ImageExtractor


def test_ocr_extracts_legible_text_from_all_samples(fixtures_dir: Path) -> None:
    extractor = ImageExtractor()
    sample_files = sorted((fixtures_dir / "images").glob("*.png"))
    assert len(sample_files) == 10

    for path in sample_files:
        text = extractor.extract(path)
        # OCR output isn't guaranteed byte-exact, so assert on substrings
        # that must survive legible recognition rather than full equality.
        assert "Product ID" in text
        assert "Ingredients" in text

        # The product ID embedded in the filename should round-trip through OCR.
        match = re.search(r"(P-\d{4}-\d{4})", path.stem)
        assert match is not None
        assert match.group(1) in text
