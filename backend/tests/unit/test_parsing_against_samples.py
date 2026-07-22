import csv
import json
from pathlib import Path

from app.domain.extraction.detector import FileType, detect_file_type
from app.domain.extraction.image_extractor import ImageExtractor
from app.domain.extraction.pdf_extractor import PdfExtractor
from app.domain.extraction.text_extractor import TextExtractor
from app.domain.parsing.product_parser import parse_product_text

_EXTRACTORS = {
    FileType.PDF: PdfExtractor(),
    FileType.IMAGE: ImageExtractor(),
    FileType.TEXT: TextExtractor(),
}


def test_parsed_fields_match_expected_for_all_30_samples(fixtures_dir: Path) -> None:
    expected = json.loads((fixtures_dir / "expected_ingredients.json").read_text())
    with (fixtures_dir / "product_index.csv").open(newline="", encoding="utf-8") as f:
        index_rows = list(csv.DictReader(f))

    assert len(index_rows) == 30

    for row in index_rows:
        product_id = row["product_id"]
        path = fixtures_dir / row["filename"]
        file_type = detect_file_type(path)
        raw_text = _EXTRACTORS[file_type].extract(path)

        product = parse_product_text(raw_text)
        expected_product = expected[product_id]

        assert product.product_name == expected_product["product_name"], product_id
        assert product.sku == expected_product["sku"], product_id
        assert product.ingredients == expected_product["ingredients"], product_id
        assert product.needs_llm_fallback == expected_product["needs_llm_fallback"], product_id
