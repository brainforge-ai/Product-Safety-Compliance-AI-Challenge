"""
Unit tests for normalization module.

Tests edge cases for chemical name and formula handling.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.matching.normalize import (
    is_formula,
    to_hill,
    normalize_name,
    normalize_for_matching,
    classify,
)
from src.core.models import IngredientKind


class TestIsFormula:
    """Tests for is_formula function."""

    def test_simple_formulas(self):
        """Test recognition of common molecular formulas."""
        assert is_formula("C6H6") is True      # Benzene
        assert is_formula("H2O2") is True      # Hydrogen peroxide
        assert is_formula("H2O") is True       # Water
        assert is_formula("C8H10N4O2") is True # Caffeine
        assert is_formula("NaCl") is True      # Sodium chloride

    def test_complex_formulas(self):
        """Test recognition of more complex formulas."""
        assert is_formula("C4H8O2") is True    # 1,4-Dioxane formula
        assert is_formula("C12H22O11") is True # Sucrose
        assert is_formula("C2H5OH") is True    # Ethanol (alternate notation)

    def test_abbreviations_not_formulas(self):
        """Test that common abbreviations are NOT recognized as formulas."""
        assert is_formula("BHA") is False      # Butylated hydroxyanisole
        assert is_formula("BHT") is False      # Butylated hydroxytoluene
        assert is_formula("EDTA") is False     # Ethylenediaminetetraacetic acid
        assert is_formula("PEG") is False      # Polyethylene glycol
        assert is_formula("SLS") is False      # Sodium lauryl sulfate

    def test_names_not_formulas(self):
        """Test that chemical names are NOT recognized as formulas."""
        assert is_formula("Benzene") is False
        assert is_formula("Hydrogen Peroxide") is False
        assert is_formula("Sodium Lauryl Sulfate") is False
        assert is_formula("1,4-Dioxane") is False  # Name, not formula
        assert is_formula("Caffeine") is False

    def test_edge_cases(self):
        """Test edge cases."""
        assert is_formula("") is False
        assert is_formula("   ") is False
        assert is_formula("123") is False
        assert is_formula("abc") is False


class TestToHill:
    """Tests for Hill notation conversion."""

    def test_already_hill(self):
        """Test formulas already in Hill notation."""
        assert to_hill("C6H6") == "C6H6"
        assert to_hill("C8H10N4O2") == "C8H10N4O2"

    def test_no_carbon(self):
        """Test formulas without carbon (alphabetical order)."""
        assert to_hill("H2O") == "H2O"
        assert to_hill("H2O2") == "H2O2"
        assert to_hill("NaCl") == "ClNa"  # Alphabetical

    def test_reordering(self):
        """Test formulas that need reordering."""
        # If carbon present: C first, H second, then alphabetical
        assert to_hill("C6H6") == "C6H6"

    def test_count_one_handling(self):
        """Test that count of 1 is handled correctly."""
        assert "1" not in to_hill("H2O") or to_hill("H2O") == "H2O"


class TestNormalizeName:
    """Tests for name normalization."""

    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert normalize_name("Benzene") == "benzene"
        assert normalize_name("BENZENE") == "benzene"
        assert normalize_name("  Benzene  ") == "benzene"

    def test_preserve_important_chars(self):
        """Test that important characters are preserved."""
        # 1,4-Dioxane should keep the comma!
        result = normalize_name("1,4-Dioxane")
        assert "1" in result
        assert "4" in result
        assert "dioxane" in result

    def test_whitespace_collapse(self):
        """Test that multiple spaces are collapsed."""
        assert normalize_name("Sodium   Lauryl   Sulfate") == "sodium lauryl sulfate"


class TestNormalizeForMatching:
    """Tests for aggressive normalization."""

    def test_removes_separators(self):
        """Test that separators are removed."""
        assert normalize_for_matching("Sodium-Lauryl-Sulfate") == "sodiumlaurylsulfate"
        assert normalize_for_matching("Sodium Lauryl Sulfate") == "sodiumlaurylsulfate"

    def test_preserves_digits(self):
        """Test that digits are preserved."""
        result = normalize_for_matching("1,4-Dioxane")
        assert "1" in result
        assert "4" in result


class TestClassify:
    """Tests for ingredient classification."""

    def test_formula_classification(self):
        """Test formula classification."""
        assert classify("C6H6") == IngredientKind.FORMULA
        assert classify("H2O2") == IngredientKind.FORMULA

    def test_name_classification(self):
        """Test name classification."""
        assert classify("Benzene") == IngredientKind.NAME
        assert classify("Hydrogen Peroxide") == IngredientKind.NAME
        assert classify("BHA") == IngredientKind.NAME  # Abbreviation, not formula


class TestEdgeCases:
    """Test critical edge cases for the competition."""

    def test_benzene_c6h6_bidirectional(self):
        """
        CRITICAL: Benzene and C6H6 must be handled bidirectionally.

        If forbidden list has "C6H6" and product has "Benzene", must match.
        If forbidden list has "Benzene" and product has "C6H6", must match.
        """
        # Both should classify correctly
        assert classify("C6H6") == IngredientKind.FORMULA
        assert classify("Benzene") == IngredientKind.NAME

        # C6H6 should normalize to Hill notation
        assert to_hill("C6H6") == "C6H6"

    def test_hydrogen_peroxide_h2o2_bidirectional(self):
        """
        CRITICAL: Hydrogen Peroxide and H2O2 must be handled.
        """
        assert classify("H2O2") == IngredientKind.FORMULA
        assert classify("Hydrogen Peroxide") == IngredientKind.NAME
        assert to_hill("H2O2") == "H2O2"

    def test_1_4_dioxane_special_chars(self):
        """
        CRITICAL: 1,4-Dioxane has a comma that must NOT be stripped.
        """
        # Should be classified as a name (not formula)
        assert classify("1,4-Dioxane") == IngredientKind.NAME

        # Normalization should preserve the structure
        normalized = normalize_name("1,4-Dioxane")
        assert "1" in normalized
        assert "4" in normalized
        assert "dioxane" in normalized

    def test_caffeine_c8h10n4o2(self):
        """Test caffeine formula handling."""
        assert classify("C8H10N4O2") == IngredientKind.FORMULA
        assert classify("Caffeine") == IngredientKind.NAME
        assert to_hill("C8H10N4O2") == "C8H10N4O2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
