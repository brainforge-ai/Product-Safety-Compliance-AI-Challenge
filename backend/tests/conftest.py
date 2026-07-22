import csv
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def product_index() -> list[dict[str, str]]:
    with (FIXTURES_DIR / "product_index.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
