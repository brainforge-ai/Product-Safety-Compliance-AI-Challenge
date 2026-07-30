from app.domain.matching.fuzzy_matcher import FuzzyMatcher


def test_matches_close_typo() -> None:
    result = FuzzyMatcher().match("Coumarinn", "Coumarin")
    assert result is not None
    assert result.method == "fuzzy"


def test_does_not_match_sles_against_sls_at_production_threshold() -> None:
    # P-2025-0024 canary: "Sodium Laureth Sulfate" (SLES) is a different
    # real ingredient from forbidden "Sodium Lauryl Sulfate" (SLS). Every
    # standard string-similarity metric scores this pair (~85-91) higher
    # than the README's own Glucose/D-Glucopyranose fuzzy example (~65-76),
    # so no threshold can catch that example without wrongly rejecting this
    # real, clean product. The threshold is set to protect this case.
    result = FuzzyMatcher().match("Sodium Laureth Sulfate", "Sodium Lauryl Sulfate")
    assert result is None


def test_does_not_match_unrelated_ingredients() -> None:
    assert FuzzyMatcher().match("Water", "Triclosan") is None


def test_never_fuzzy_matches_distinct_long_formulas() -> None:
    assert FuzzyMatcher().match("C100H200O2", "C100H200O3") is None


def test_custom_threshold_is_respected() -> None:
    lenient = FuzzyMatcher(threshold=50.0)
    result = lenient.match("Sodium Laureth Sulfate", "Sodium Lauryl Sulfate")
    assert result is not None
