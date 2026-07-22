from app.domain.normalization.text_normalizer import normalize_text


def test_idempotent() -> None:
    for text in ["Sodium Hydroxide", "1,4-Dioxane", "  C6H6  ", "BHT"]:
        once = normalize_text(text)
        assert normalize_text(once) == once


def test_case_punctuation_and_whitespace_differences_collapse_to_the_same_value() -> None:
    variants = [
        "Sodium Hydroxide",
        "sodium-hydroxide",
        "SODIUM HYDROXIDE",
        "Sodium  Hydroxide",
        "  sodium.hydroxide  ",
    ]
    normalized = {normalize_text(v) for v in variants}
    assert len(normalized) == 1


def test_comma_bearing_ingredient_normalizes_consistently_regardless_of_spacing() -> None:
    assert normalize_text("1,4-Dioxane") == normalize_text("1, 4-Dioxane")
    assert normalize_text("1,4-Dioxane") == normalize_text("1,4 Dioxane")


def test_unicode_is_normalized_via_nfkc() -> None:
    # U+FF43 (fullwidth 'c') NFKC-normalizes to ASCII 'c'.
    assert normalize_text("ｃＶ") == normalize_text("cv")
