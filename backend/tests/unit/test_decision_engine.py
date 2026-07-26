from app.domain.decision.engine import decide, merge_llm_matches, unresolved_ingredients
from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import ExtractedProduct, MatchMethod, MatchResult

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


def test_unresolved_ingredients_excludes_matched_text() -> None:
    product = ExtractedProduct(
        product_name="Pure Lotion", ingredients=["Water", "Coumarin", "Glycerin"]
    )

    result = decide(product, FORBIDDEN_LIST, _pipeline())

    assert unresolved_ingredients(product, result) == ["Water", "Glycerin"]


def test_unresolved_ingredients_is_everything_when_nothing_matched() -> None:
    product = ExtractedProduct(product_name="Clean Serum", ingredients=["Water", "Glycerin"])

    result = decide(product, FORBIDDEN_LIST, _pipeline())

    assert unresolved_ingredients(product, result) == ["Water", "Glycerin"]


def test_merge_llm_matches_is_noop_when_llm_found_nothing() -> None:
    product = ExtractedProduct(product_name="Clean Serum", ingredients=["Water"])
    result = decide(product, FORBIDDEN_LIST, _pipeline())

    merged = merge_llm_matches(result, [])

    assert merged == result


def test_merge_llm_matches_flips_accepted_to_rejected() -> None:
    product = ExtractedProduct(
        product_name="Clean Serum", ingredients=["Water", "D-Glucopyranose"]
    )
    result = decide(product, FORBIDDEN_LIST, _pipeline())
    assert result.status == "Accepted"

    llm_match = MatchResult(
        forbidden_ingredient="Glucose",
        matched_text="D-Glucopyranose",
        method=MatchMethod.LLM,
        confidence=0.92,
    )

    merged = merge_llm_matches(result, [llm_match])

    assert merged.status == "Rejected"
    assert merged.reason == ["Contains Glucose"]
    assert merged.matches == [llm_match]


def test_merge_llm_matches_appends_to_existing_rule_based_matches() -> None:
    product = ExtractedProduct(
        product_name="Pure Lotion", ingredients=["Coumarin", "D-Glucopyranose"]
    )
    result = decide(product, FORBIDDEN_LIST, _pipeline())
    assert result.status == "Rejected"
    assert len(result.matches) == 1

    llm_match = MatchResult(
        forbidden_ingredient="Glucose",
        matched_text="D-Glucopyranose",
        method=MatchMethod.LLM,
        confidence=0.92,
    )

    merged = merge_llm_matches(result, [llm_match])

    assert merged.status == "Rejected"
    assert merged.reason == ["Contains Coumarin", "Contains Glucose"]
    assert len(merged.matches) == 2
