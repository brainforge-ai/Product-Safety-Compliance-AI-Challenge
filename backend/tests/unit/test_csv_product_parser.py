from app.domain.parsing.csv_product_parser import parse_csv_row


def test_parses_row_with_canonical_column_names() -> None:
    row = {
        "product_id": "P-2025-0099",
        "product_name": "Synthetic Serum",
        "sku": "ABC123",
        "description": "A synthetic test product.",
        "ingredients": "Water;Coumarin;C6H6",
    }

    product = parse_csv_row(row)

    assert product.product_id == "P-2025-0099"
    assert product.product_name == "Synthetic Serum"
    assert product.sku == "ABC123"
    assert product.description == "A synthetic test product."
    assert product.ingredients == ["Water", "Coumarin", "C6H6"]
    assert product.needs_llm_fallback is False


def test_parses_row_with_human_readable_column_names_case_insensitively() -> None:
    row = {
        "Product ID": "P-2025-0100",
        "Product Name": "Another Serum",
        "SKU": "XYZ789",
        "Ingredients / Chemical Formulas": "BHT|Triclosan",
    }

    product = parse_csv_row(row)

    assert product.product_id == "P-2025-0100"
    assert product.product_name == "Another Serum"
    assert product.ingredients == ["BHT", "Triclosan"]


def test_comma_bearing_ingredient_is_preserved_since_comma_is_not_a_delimiter() -> None:
    row = {"product_name": "Test", "ingredients": "1,4-Dioxane;BHT"}

    product = parse_csv_row(row)

    assert product.ingredients == ["1,4-Dioxane", "BHT"]


def test_comma_delimited_cell_preserves_chemical_and_parenthetical_commas() -> None:
    row = {
        "product_name": "Test",
        "ingredient list": "Water, Glycerin, 1,4-Dioxane, Fragrance (Parfum, Aroma)",
    }

    product = parse_csv_row(row)

    assert product.ingredients == [
        "Water",
        "Glycerin",
        "1,4-Dioxane",
        "Fragrance (Parfum, Aroma)",
    ]


def test_extra_csv_columns_do_not_crash_header_normalization() -> None:
    product = parse_csv_row({"Product Name": "X", "Ingredients": "Water", None: "extra"})

    assert product.ingredients == ["Water"]


def test_missing_ingredients_column_sets_llm_fallback_flag() -> None:
    row = {"product_name": "No Ingredients Product"}

    product = parse_csv_row(row)

    assert product.ingredients == []
    assert product.needs_llm_fallback is True


def test_missing_product_name_defaults_to_unknown() -> None:
    row = {"ingredients": "Water"}

    product = parse_csv_row(row)

    assert product.product_name == "Unknown Product"
