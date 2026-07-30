from app.domain.normalization.formula_parser import formulas_equal, is_formula, parse_formula


def test_parses_simple_formulas() -> None:
    assert parse_formula("C6H6") == {"C": 6, "H": 6}
    assert parse_formula("H2O2") == {"H": 2, "O": 2}
    assert parse_formula("NaCl") == {"Na": 1, "Cl": 1}


def test_element_without_trailing_digit_defaults_to_count_one() -> None:
    assert parse_formula("NaCl") == {"Na": 1, "Cl": 1}


def test_repeated_element_tokens_accumulate() -> None:
    # Not present in the sample dataset, but the parser must not silently
    # overwrite a repeated element token.
    assert parse_formula("CH3COOH") == {"C": 2, "H": 4, "O": 2}


def test_order_independent_equality() -> None:
    assert formulas_equal("H2O2", "O2H2") is True
    assert formulas_equal("C6H8O7", "O7C6H8") is True


def test_different_formulas_are_not_equal() -> None:
    assert formulas_equal("C6H6", "H2O2") is False


def test_rejects_plain_ingredient_names() -> None:
    assert is_formula("Sodium Hydroxide") is False
    assert parse_formula("Sodium Hydroxide") is None


def test_rejects_acronym_with_invalid_element_token() -> None:
    # "BHT": B and H are valid elements, but "T" is not.
    assert is_formula("BHT") is False


def test_rejects_digit_led_ingredient_name() -> None:
    assert is_formula("1,4-Dioxane") is False


def test_parses_nested_parentheses() -> None:
    assert parse_formula("Mg(OH)2") == {"Mg": 1, "O": 2, "H": 2}
    assert formulas_equal("Ca(OH)2", "CaO2H2") is True


def test_parses_hydrate_notation() -> None:
    expected = {"Cu": 1, "S": 1, "O": 9, "H": 10}
    assert parse_formula("CuSO4.5H2O") == expected
    assert parse_formula("CuSO4·5H2O") == expected


def test_ocr_corrupted_formula_is_still_formula_shaped_but_parses_wrong() -> None:
    # Documents why correction is deferred to Phase 5: is_formula stays
    # permissive so a corrupted string still routes into the formula tier,
    # but a context-free strict parse cannot recover the true value.
    assert is_formula("H202") is True
    assert parse_formula("H202") == {"H": 202}
    assert formulas_equal("H202", "H2O2") is False
