from pathlib import Path

from app.domain.extraction.csv_extractor import CsvExtractor


def test_extracts_rows_as_dicts(tmp_path: Path) -> None:
    path = tmp_path / "product.csv"
    path.write_text(
        "Product ID,Product Name,SKU,Ingredients\n"
        "P-2025-0099,Synthetic Serum,ABC123,Water;Coumarin;C6H6\n",
        encoding="utf-8",
    )

    rows = CsvExtractor().extract(path)

    assert rows == [
        {
            "Product ID": "P-2025-0099",
            "Product Name": "Synthetic Serum",
            "SKU": "ABC123",
            "Ingredients": "Water;Coumarin;C6H6",
        }
    ]


def test_extracts_multiple_rows(tmp_path: Path) -> None:
    path = tmp_path / "products.csv"
    path.write_text(
        "Product ID,Product Name\nP-1,First\nP-2,Second\n",
        encoding="utf-8",
    )

    rows = CsvExtractor().extract(path)

    assert len(rows) == 2
    assert rows[0]["Product Name"] == "First"
    assert rows[1]["Product Name"] == "Second"
