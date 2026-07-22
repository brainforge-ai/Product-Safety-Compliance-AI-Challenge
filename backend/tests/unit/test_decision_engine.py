from app.domain.decision.engine import decide
from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import ExtractedProduct

FORBIDDEN_LIST = ["Coumarin", "C6H6", "Propylparaben"]


def _pipeline() -> MatchPipeline:
    return MatchPipeline([ExactMatcher(), FormulaMatcher(), FuzzyMatcher(), AcronymMatcher()])


def test_accepts_product_with_no_forbidden_ingredients() -> None:
    product = ExtractedProduct(product_name="Clean Serum", ingredients=["Water", "Glycerin"])

    result = decide(product, FORBIDDEN_LIST, _pipeline())

    assert result.status == "Accepted"
    assert result.reason == []
    assert result.matches == []


def test_rejects_product_with_a_forbidden_ingredient() -> None:
    product = ExtractedProduct(
        product_name="Pure Lotion", ingredients=["Water", "Coumarin", "Propylparaben"]
    )

    result = decide(product, FORBIDDEN_LIST, _pipeline())

    assert result.status == "Rejected"
    assert result.reason == ["Contains Coumarin", "Contains Propylparaben"]
    assert len(result.matches) == 2


def test_deduplicates_reason_when_multiple_ingredients_hit_the_same_forbidden_entry() -> None:
    product = ExtractedProduct(
        product_name="Odd Product", ingredients=["Coumarin", "coumarin", "C6H6"]
    )

    result = decide(product, FORBIDDEN_LIST, _pipeline())

    assert result.status == "Rejected"
    assert result.reason == ["Contains Coumarin", "Contains C6H6"]
    assert len(result.matches) == 3
