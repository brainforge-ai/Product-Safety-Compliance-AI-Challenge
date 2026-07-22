from pathlib import Path

from app.domain.extraction.text_extractor import TextExtractor


def test_extracts_raw_content_verbatim(fixtures_dir: Path) -> None:
    extractor = TextExtractor()
    sample_files = sorted((fixtures_dir / "texts").glob("*.txt"))
    assert len(sample_files) == 10

    for path in sample_files:
        text = extractor.extract(path)
        assert text == path.read_text(encoding="utf-8")
        assert "Product ID" in text
        assert "Ingredients" in text
