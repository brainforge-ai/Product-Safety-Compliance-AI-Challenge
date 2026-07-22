from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.pipeline import MatchPipeline

FORBIDDEN_LIST = ["Coumarin", "C6H6", "BHA", "Propylparaben"]


def _default_pipeline() -> MatchPipeline:
    return MatchPipeline([ExactMatcher(), FormulaMatcher(), FuzzyMatcher(), AcronymMatcher()])


def test_pipeline_returns_first_confident_match_across_tiers() -> None:
    pipeline = _default_pipeline()

    exact = pipeline.match_ingredient("Coumarin", FORBIDDEN_LIST)
    assert exact is not None and exact.method == "exact"

    # Reordered so it can't be caught by the exact tier's string comparison,
    # only by the formula tier's order-independent parsing.
    formula = pipeline.match_ingredient("H6C6", FORBIDDEN_LIST)
    assert formula is not None and formula.method == "formula"

    acronym = pipeline.match_ingredient("Butylated Hydroxy Anisole", FORBIDDEN_LIST)
    assert acronym is not None and acronym.method == "acronym"


def test_pipeline_stops_at_earliest_matching_tier_not_a_later_one() -> None:
    # "Coumarin" would also fuzzy-match itself; confirm the pipeline reports
    # the earliest tier (exact), not a later one, when both would fire.
    pipeline = _default_pipeline()
    result = pipeline.match_ingredient("Coumarin", FORBIDDEN_LIST)
    assert result is not None
    assert result.method == "exact"


def test_pipeline_returns_none_for_safe_ingredient() -> None:
    pipeline = _default_pipeline()
    assert pipeline.match_ingredient("Water", FORBIDDEN_LIST) is None


def test_pipeline_checks_every_forbidden_entry_at_each_tier() -> None:
    pipeline = _default_pipeline()
    result = pipeline.match_ingredient("Propylparaben", FORBIDDEN_LIST)
    assert result is not None
    assert result.forbidden_ingredient == "Propylparaben"


def test_pipeline_is_extensible_with_additional_matchers() -> None:
    class AlwaysMatches:
        def match(self, ingredient: str, forbidden_entry: str):
            from app.domain.models import MatchMethod, MatchResult

            return MatchResult(
                forbidden_ingredient=forbidden_entry,
                matched_text=ingredient,
                method=MatchMethod.EMBEDDING,
                confidence=0.5,
            )

    pipeline = MatchPipeline([ExactMatcher(), AlwaysMatches()])
    result = pipeline.match_ingredient("Water", FORBIDDEN_LIST)
    assert result is not None
    assert result.method == "embedding"
