"""Regression guard for tier 5 against the real embedding model.

This is the test that actually protects the system: per-matcher unit tests
in test_embedding_matcher.py use a fake encoder and can't catch a bad
threshold choice or a formula-exclusion regression against real data. This
test runs the full 30-sample ledger with the real MiniLM model wired into
the pipeline at the production threshold and confirms the hand-derived
Accept/Reject ledger (docs/IMPLEMENTATION_PLAN.md Phase 5) still holds --
especially P-2025-0024, whose Accepted status is the binding constraint on
the tier-5 threshold (see embedding_matcher.py's module docstring).

Skipped unless the MiniLM weights are already cached locally, so this never
makes a network call and `pytest` still passes fully offline by default
(ARCHITECTURE.md Section 13) -- this test only ever runs as an opt-in local
check after `pip install -r requirements-ai.txt` and one warm run.
"""

import csv
from pathlib import Path

import pytest

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


def _embedding_model_available() -> bool:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return False
    try:
        SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _embedding_model_available(),
    reason=(
        "sentence-transformers not installed or MiniLM weights not cached locally; "
        "this test must never touch the network (ARCHITECTURE.md Section 13)."
    ),
)


def _build_pipeline_with_embeddings() -> MatchPipeline:
    from app.domain.matching.embedding_matcher import EmbeddingMatcher
    from app.infra.embeddings.sentence_transformer_encoder import SentenceTransformerEncoder

    return MatchPipeline(
        [
            ExactMatcher(),
            FormulaMatcher(),
            FuzzyMatcher(),
            AcronymMatcher(),
            EmbeddingMatcher(SentenceTransformerEncoder()),
        ]
    )


def test_all_30_samples_match_the_ledger_with_embedding_tier_enabled(
    fixtures_dir: Path, expected_accepted_product_ids: set[str]
) -> None:
    repo = ForbiddenListRepository.from_csv(fixtures_dir / "forbidden_ingredients.csv")
    forbidden_list = repo.get_all()
    pipeline = _build_pipeline_with_embeddings()

    with (fixtures_dir / "product_index.csv").open(newline="", encoding="utf-8") as f:
        index_rows = list(csv.DictReader(f))

    for row in index_rows:
        product_id = row["product_id"]
        path = fixtures_dir / row["filename"]
        file_type = detect_file_type(path)
        raw_text = _EXTRACTORS[file_type].extract(path)
        product = parse_product_text(raw_text)

        result = decide(product, forbidden_list, pipeline)

        expected_status = "Accepted" if product_id in expected_accepted_product_ids else "Rejected"
        assert result.status == expected_status, (
            f"{product_id}: expected {expected_status}, got {result.status} "
            f"(reasons={result.reason}) -- tier 5 threshold may be catching a false positive"
        )
