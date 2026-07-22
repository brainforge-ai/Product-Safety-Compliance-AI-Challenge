from app.domain.matching.formula_matcher import FormulaMatcher


def test_matches_identical_formula() -> None:
    result = FormulaMatcher().match("C6H6", "C6H6")
    assert result is not None
    assert result.method == "formula"
    assert result.confidence == 1.0


def test_matches_reordered_elements() -> None:
    result = FormulaMatcher().match("O2H2", "H2O2")
    assert result is not None
    assert result.confidence == 1.0


def test_no_match_for_different_formula() -> None:
    assert FormulaMatcher().match("C6H6", "H2O2") is None


def test_does_not_apply_when_forbidden_entry_is_not_a_formula() -> None:
    # Even if the ingredient happens to be formula-shaped, this tier only
    # fires when the forbidden entry itself is a formula.
    assert FormulaMatcher().match("C6H6", "Coumarin") is None


def test_corrects_single_ocr_zero_for_o_misread() -> None:
    # The P-2025-0026 canary: H2O2 scanned as H202.
    result = FormulaMatcher().match("H202", "H2O2")
    assert result is not None
    assert result.method == "formula"
    assert result.confidence < 1.0


def test_corrects_ocr_zero_without_disturbing_legitimate_digit_counts() -> None:
    # C20H40O2 scanned as C20H4002: the first two zeros are legitimate count
    # digits ("20", "40"); only the third is a misread 'O'.
    result = FormulaMatcher().match("C20H4002", "C20H40O2")
    assert result is not None


def test_corrects_leading_euro_sign_misread_as_c() -> None:
    result = FormulaMatcher().match("€12H24012", "C12H24O12")
    assert result is not None


def test_does_not_over_correct_to_a_different_formula() -> None:
    # H202's "true" correction is H2O2, not any other forbidden formula.
    assert FormulaMatcher().match("H202", "C6H6") is None
