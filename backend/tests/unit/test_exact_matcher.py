from app.domain.matching.exact_matcher import ExactMatcher


def test_matches_identical_text() -> None:
    result = ExactMatcher().match("Coumarin", "Coumarin")
    assert result is not None
    assert result.forbidden_ingredient == "Coumarin"
    assert result.matched_text == "Coumarin"
    assert result.method == "exact"
    assert result.confidence == 1.0


def test_matches_despite_case_punctuation_and_whitespace_differences() -> None:
    result = ExactMatcher().match("  coumarin  ", "Coumarin")
    assert result is not None

    result = ExactMatcher().match("1, 4-Dioxane", "1,4-Dioxane")
    assert result is not None


def test_no_match_for_different_ingredients() -> None:
    assert ExactMatcher().match("Water", "Coumarin") is None


def test_no_match_for_empty_ingredient() -> None:
    assert ExactMatcher().match("", "Coumarin") is None
