from app.domain.parsing.product_parser import parse_product_text


def test_parses_all_fields_from_well_formed_text() -> None:
    text = (
        "Product ID: P-2025-0001\n"
        "Product Name: Pure Lotion\n"
        "SKU: ABC123\n"
        "Description:\n"
        "A pure lotion for everyday use.\n"
        "Ingredients / Chemical Formulas:\n"
        "- Coumarin\n"
        "- C6H6\n"
    )

    product = parse_product_text(text)

    assert product.product_id == "P-2025-0001"
    assert product.product_name == "Pure Lotion"
    assert product.sku == "ABC123"
    assert product.description == "A pure lotion for everyday use."
    assert product.ingredients == ["Coumarin", "C6H6"]
    assert product.needs_llm_fallback is False


def test_joins_multi_line_description() -> None:
    text = (
        "Product Name: Daily Lotion\n"
        "Description:\n"
        "A daily lotion formulated with selected active compounds for\n"
        "everyday use.\n"
        "Ingredients / Chemical Formulas:\n"
        "- NaCl\n"
    )

    product = parse_product_text(text)

    assert product.description == (
        "A daily lotion formulated with selected active compounds for everyday use."
    )


def test_tolerates_extra_blank_lines_between_fields() -> None:
    text = (
        "Product ID: P-2025-0017\n"
        "\n"
        "Product Name: Daily Lotion\n"
        "SKU: AC56T4UF\n"
        "\n"
        "Description:\n"
        "A daily lotion.\n"
        "\n"
        "Ingredients / Chemical Formulas:\n"
        "- Panthenol\n"
    )

    product = parse_product_text(text)

    assert product.product_id == "P-2025-0017"
    assert product.product_name == "Daily Lotion"
    assert product.sku == "AC56T4UF"
    assert product.ingredients == ["Panthenol"]


def test_handles_varied_bullet_characters_and_numbering() -> None:
    text = (
        "Ingredients / Chemical Formulas:\n"
        "- Coumarin\n"
        "* BHT\n"
        "• Triclosan\n"
        "1. Formaldehyde\n"
        "2) Propylparaben\n"
    )

    product = parse_product_text(text)

    assert product.ingredients == [
        "Coumarin",
        "BHT",
        "Triclosan",
        "Formaldehyde",
        "Propylparaben",
    ]


def test_does_not_mistake_a_comma_bearing_ingredient_for_a_numbered_marker() -> None:
    # "1,4-Dioxane" starts with a digit but is a single ingredient name, not
    # a "1." list marker; the bullet stripper must not truncate it.
    text = "Ingredients / Chemical Formulas:\n- 1,4-Dioxane\n- BHT\n"

    product = parse_product_text(text)

    assert product.ingredients == ["1,4-Dioxane", "BHT"]


def test_numbered_marker_followed_by_digit_leading_ingredient_still_strips_only_marker() -> None:
    text = "Ingredients / Chemical Formulas:\n1. 1,4-Dioxane\n2. BHT\n"

    product = parse_product_text(text)

    assert product.ingredients == ["1,4-Dioxane", "BHT"]


def test_missing_ingredients_section_sets_llm_fallback_flag() -> None:
    text = "Product Name: Mystery Serum\nSKU: XYZ\nDescription:\nNo ingredients listed here.\n"

    product = parse_product_text(text)

    assert product.ingredients == []
    assert product.needs_llm_fallback is True


def test_missing_product_name_defaults_to_unknown() -> None:
    text = "Ingredients / Chemical Formulas:\n- Water\n"

    product = parse_product_text(text)

    assert product.product_name == "Unknown Product"
    assert product.ingredients == ["Water"]


def test_parses_common_inline_ingredients_header_and_stops_at_warnings() -> None:
    text = (
        "Product Name: Generalized Label\n"
        "Ingredients: Water, Glycerin, 1,4-Dioxane, Fragrance (Parfum, Aroma)\n"
        "Warnings: For external use only\n"
    )

    product = parse_product_text(text)

    assert product.ingredients == [
        "Water",
        "Glycerin",
        "1,4-Dioxane",
        "Fragrance (Parfum, Aroma)",
    ]


def test_parses_plain_ingredient_list_header_with_bullets() -> None:
    text = "Product Name: X\nIngredient List:\n• Water\n• Coumarin\nDirections: Rinse\n"

    product = parse_product_text(text)

    assert product.ingredients == ["Water", "Coumarin"]
