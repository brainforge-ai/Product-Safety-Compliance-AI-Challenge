from app.domain.matching.acronym_matcher import AcronymMatcher


def test_matches_acronym_against_spelled_out_name() -> None:
    result = AcronymMatcher().match("BHA", "Butylated Hydroxy Anisole")
    assert result is not None
    assert result.method == "acronym"
    assert result.forbidden_ingredient == "Butylated Hydroxy Anisole"
    assert result.matched_text == "BHA"


def test_matches_regardless_of_which_side_is_the_acronym() -> None:
    result = AcronymMatcher().match("Butylated Hydroxy Anisole", "BHA")
    assert result is not None
    assert result.forbidden_ingredient == "BHA"
    assert result.matched_text == "Butylated Hydroxy Anisole"


def test_no_match_when_initials_differ() -> None:
    assert AcronymMatcher().match("BHT", "Butylated Hydroxy Anisole") is None


def test_no_match_for_single_word_name() -> None:
    assert AcronymMatcher().match("BHT", "Triclosan") is None


def test_no_match_when_neither_side_looks_like_an_acronym() -> None:
    assert AcronymMatcher().match("Sodium Hydroxide", "Sodium Citrate") is None


def test_does_not_treat_formula_as_an_acronym() -> None:
    # "H2O2" is not alphabetic, so it must never be treated as an acronym
    # candidate even though it is short and uppercase.
    assert AcronymMatcher().match("H2O2", "Hydrogen Two Oxide Two") is None
