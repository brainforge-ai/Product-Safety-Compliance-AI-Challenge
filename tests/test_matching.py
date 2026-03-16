from types import SimpleNamespace

from app.config import expand_forbidden_synonyms
import app.config as config_module
import app.extraction.normalizer as normalizer_module
from app.extraction.normalizer import get_pubchem_synonyms, normalize, resolve_formula_to_name
from app.extraction.ingredient_parser import extract_ingredients
from app.ingestion.image_ocr import _group_ocr_results_into_lines
from app.pipeline import _expand_candidate_ingredients
from app.matching.embedding_matcher import embedding_match


def _fake_pubchem_lookup(identifier, namespace):
    key = (str(identifier).lower(), namespace)
    mapping = {
        ("h2o", "formula"): [SimpleNamespace(iupac_name="Oxidane", synonyms=["Water", "H2O"])],
        ("h2o2", "formula"): [SimpleNamespace(iupac_name="Hydrogen Peroxide", synonyms=["Hydrogen Peroxide", "H2O2"])],
        ("c6h12o6", "formula"): [SimpleNamespace(iupac_name="Glucose", synonyms=["Glucose", "D-Glucose", "C6H12O6"])],
        ("sulfuric acid", "name"): [SimpleNamespace(iupac_name="Sulfuric Acid", synonyms=["Sulfuric Acid", "H2SO4", "H₂SO₄"])],
        ("sodium chloride", "name"): [SimpleNamespace(iupac_name="Sodium Chloride", synonyms=["Sodium Chloride", "NaCl"])],
        ("water", "name"): [SimpleNamespace(iupac_name="Oxidane", synonyms=["Water", "H2O"])],
    }
    return mapping.get(key, [])


def setup_function():
    resolve_formula_to_name.cache_clear()
    get_pubchem_synonyms.cache_clear()
    normalizer_module._get_pubchem_compounds.cache_clear()


def test_formula_resolves_to_canonical_name_via_pubchem(monkeypatch):
    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _fake_pubchem_lookup)
    assert normalize("H₂O₂") == "hydrogen peroxide"


def test_h2o_resolves_to_water_not_formula_or_obscure_name(monkeypatch):
    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _fake_pubchem_lookup)
    assert normalize("H2O") == "water"


def test_forbidden_name_expands_to_formula_synonym_via_pubchem(monkeypatch):
    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _fake_pubchem_lookup)
    monkeypatch.setattr(config_module.pcp, "get_compounds", _fake_pubchem_lookup)
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Sodium Chloride"])
    matches = embedding_match(
        [normalize("NaCl")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "sodium chloride"


def test_water_forbidden_matches_h2o_formula_via_pubchem(monkeypatch):
    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _fake_pubchem_lookup)
    monkeypatch.setattr(config_module.pcp, "get_compounds", _fake_pubchem_lookup)
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Water"])
    matches = embedding_match(
        [normalize("H2O")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "water"


def test_formula_with_subscripts_and_synonyms_matches_generic_pubchem_result(monkeypatch):
    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _fake_pubchem_lookup)
    monkeypatch.setattr(config_module.pcp, "get_compounds", _fake_pubchem_lookup)
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Glucose"])
    matches = embedding_match(
        [normalize("C6H12O6")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "glucose"


def test_exact_formula_match_is_detected_before_embedding_logic():
    forbidden, term_to_canonical = expand_forbidden_synonyms(["C8H10N4O2"])
    matches = embedding_match(
        [normalize("C8H10N4O2")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] in {"c8h10n4o2", "caffeine"}
    assert matches[0][2] == 1.0


def test_ingredient_parser_repairs_ocr_damaged_formula_tokens():
    text = "Ingredients: C8Hion4O2, Czoh4Oo2, C16H32O2"
    ingredients = extract_ingredients(text)
    assert "C8H10N4O2" in ingredients
    assert "CZOH4OO2" not in ingredients
    assert any(token != "Czoh4Oo2" for token in ingredients)
    assert "C16H32O2" in ingredients


def test_sulphate_spelling_variant_matches_sulfate_generically():
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Sodium Lauryl Sulfate"])
    matches = embedding_match(
        [normalize("Sodium Lauryl Sulphate")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "sodium lauryl sulfate"


def test_ingredient_parser_preserves_multi_word_ingredients_for_exact_match():
    ingredients = extract_ingredients("Ingredients: Water, Sodium Lauryl Sulfate, Glycerin")
    assert "Sodium Lauryl Sulfate" in ingredients


def test_exact_multi_word_forbidden_ingredient_matches():
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Sodium Lauryl Sulfate"])
    matches = embedding_match(
        [normalize("Sodium Lauryl Sulfate")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "sodium lauryl sulfate"
    assert matches[0][2] == 1.0


def test_long_ocr_ingredient_line_expands_multiword_candidates():
    ingredients = ["water sodium lauryl sulfate glycerin"]
    normalized = [normalize(ingredients[0])]
    expanded_original, expanded_normalized = _expand_candidate_ingredients(
        ingredients,
        normalized,
        ["sodium lauryl sulfate", "methylparaben"],
    )
    assert "sodium lauryl sulfate" in expanded_normalized


def test_long_ocr_ingredient_line_matches_forbidden_phrase():
    ingredients = ["water sodium lauryl sulfate glycerin"]
    normalized = [normalize(ingredients[0])]
    _, expanded_normalized = _expand_candidate_ingredients(
        ingredients,
        normalized,
        ["sodium lauryl sulfate"],
    )
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Sodium Lauryl Sulfate"])
    matches = embedding_match(
        expanded_normalized,
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert any(match[1] == "sodium lauryl sulfate" for match in matches)


def test_easyocr_results_preserve_newline_separated_ingredients():
    results = [
        ([[0, 0], [50, 0], [50, 10], [0, 10]], "Sodium Lauryl Sulfate", 0.99),
        ([[0, 30], [30, 30], [30, 40], [0, 40]], "Glycerin", 0.99),
        ([[0, 60], [25, 60], [25, 70], [0, 70]], "Water", 0.99),
    ]
    lines = _group_ocr_results_into_lines(results, y_tolerance=8)
    assert lines == ["Sodium Lauryl Sulfate", "Glycerin", "Water"]


def test_newline_separated_ingredient_block_keeps_multiword_ingredient():
    text = "Ingredients:\nSodium Lauryl Sulfate\nGlycerin\nWater"
    ingredients = extract_ingredients(text)
    assert "Sodium Lauryl Sulfate" in ingredients


def test_spelling_mistake_still_matches_forbidden_term():
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Methylparaben"])
    matches = embedding_match(
        [normalize("Methlyparaben")],
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    assert matches
    assert matches[0][1] == "methylparaben"


def test_embedding_fallback_does_not_create_unrelated_false_positive():
    ingredients = [
        normalize("potato"),
        normalize("edible vegetable oil"),
        normalize("iodized salt"),
        normalize("red chilli powder"),
        normalize("maltodextrin"),
        normalize("spices"),
        normalize("onion powder"),
        normalize("maida"),
        normalize("black salt"),
        normalize("milk solids"),
        normalize("sugar"),
        normalize("tomato powder"),
        normalize("hydrolysed vegetable protein"),
        normalize("malic acid"),
        normalize("citric acid"),
        normalize("tartaric acid"),
        normalize("garlic powder"),
    ]
    forbidden, term_to_canonical = expand_forbidden_synonyms([
        "Hydrogen Peroxide",
        "Methylparaben",
        "Black Salt",
        "Garlic Powder",
        "Tartaric Acid",
    ])
    matches = embedding_match(
        ingredients,
        forbidden,
        term_to_canonical,
        forbidden_set={term.strip().lower() for term in forbidden},
    )
    found = {match[1] for match in matches}
    assert "black salt" in found
    assert "garlic powder" in found
    assert "tartaric acid" in found
    assert "hydrogen peroxide" not in found
    assert "methylparaben" not in found


def test_pubchem_failure_falls_back_without_crashing(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("PubChem unavailable")

    monkeypatch.setattr(normalizer_module.pcp, "get_compounds", _raise)
    monkeypatch.setattr(config_module.pcp, "get_compounds", _raise)
    assert normalize("H2O2") == "h2o2"
    forbidden, term_to_canonical = expand_forbidden_synonyms(["Hydrogen Peroxide"])
    assert "hydrogen peroxide" in forbidden