import csv
from pathlib import Path

from app.domain.decision.engine import decide
from app.domain.extraction.detector import FileType, detect_file_type
from app.domain.extraction.image_extractor import ImageExtractor
from app.domain.extraction.pdf_extractor import PdfExtractor
from app.domain.extraction.text_extractor import TextExtractor
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.parsing.product_parser import parse_product_text

_EXTRACTORS = {
    FileType.PDF: PdfExtractor(),
    FileType.IMAGE: ImageExtractor(),
    FileType.TEXT: TextExtractor(),
}

# Hand-derived ground truth (see docs/IMPLEMENTATION_PLAN.md Phase 5 notes):
# built by manually checking each sample's real ingredients against
# forbidden_ingredients.csv, independently of this matching pipeline.
_EXPECTED_ACCEPTED = {
    "P-2025-0003",
    "P-2025-0014",
    "P-2025-0022",
    "P-2025-0024",
    "P-2025-0025",
    "P-2025-0028",
}


def _build_pipeline() -> MatchPipeline:
    return MatchPipeline([ExactMatcher(), FormulaMatcher(), FuzzyMatcher(), AcronymMatcher()])


def test_all_30_samples_match_the_hand_derived_ledger(fixtures_dir: Path) -> None:
    repo = ForbiddenListRepository.from_csv(fixtures_dir / "forbidden_ingredients.csv")
    forbidden_list = repo.get_all()
    pipeline = _build_pipeline()

    with (fixtures_dir / "product_index.csv").open(newline="", encoding="utf-8") as f:
        index_rows = list(csv.DictReader(f))

    assert len(index_rows) == 30

    for row in index_rows:
        product_id = row["product_id"]
        path = fixtures_dir / row["filename"]
        file_type = detect_file_type(path)
        raw_text = _EXTRACTORS[file_type].extract(path)
        product = parse_product_text(raw_text)

        result = decide(product, forbidden_list, pipeline)

        expected_status = "Accepted" if product_id in _EXPECTED_ACCEPTED else "Rejected"
        assert result.status == expected_status, (
            f"{product_id}: expected {expected_status}, got {result.status} "
            f"(reasons={result.reason})"
        )


def test_p2025_0026_rejects_via_formula_correction_not_fuzzy(fixtures_dir: Path) -> None:
    # The formula-correction canary: its only forbidden ingredient is
    # OCR-corrupted H202 (true H2O2). Confirm it's caught by the formula
    # tier specifically, not incidentally by fuzzy matching.
    repo = ForbiddenListRepository.from_csv(fixtures_dir / "forbidden_ingredients.csv")
    forbidden_list = repo.get_all()
    pipeline = _build_pipeline()

    path = fixtures_dir / "images" / "P-2025-0026_Radiant_Sunscreen.png"
    raw_text = ImageExtractor().extract(path)
    product = parse_product_text(raw_text)

    result = decide(product, forbidden_list, pipeline)

    assert result.status == "Rejected"
    assert result.reason == ["Contains H2O2"]
    assert result.matches[0].method == "formula"


def test_p2025_0024_stays_accepted_despite_near_miss_sles_vs_sls(fixtures_dir: Path) -> None:
    # The fuzzy false-positive canary: "Sodium Laureth Sulfate" must not be
    # confused with forbidden "Sodium Lauryl Sulfate".
    repo = ForbiddenListRepository.from_csv(fixtures_dir / "forbidden_ingredients.csv")
    forbidden_list = repo.get_all()
    pipeline = _build_pipeline()

    path = fixtures_dir / "texts" / "P-2025-0024_Pro_Conditioner.txt"
    raw_text = TextExtractor().extract(path)
    product = parse_product_text(raw_text)

    result = decide(product, forbidden_list, pipeline)

    assert result.status == "Accepted"
