import csv
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Hand-derived ground truth (see docs/IMPLEMENTATION_PLAN.md Phase 5 notes):
# built by manually checking each sample's real ingredients against
# forbidden_ingredients.csv, independently of the matching pipeline itself.
EXPECTED_ACCEPTED_PRODUCT_IDS = {
    "P-2025-0003",
    "P-2025-0014",
    "P-2025-0022",
    "P-2025-0024",
    "P-2025-0025",
    "P-2025-0028",
}


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def product_index() -> list[dict[str, str]]:
    with (FIXTURES_DIR / "product_index.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def expected_accepted_product_ids() -> set[str]:
    return EXPECTED_ACCEPTED_PRODUCT_IDS
