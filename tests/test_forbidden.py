"""
Unit tests for ForbiddenIndex.

Tests loading, Layer A matching (exact + alias), and CID matching.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.matching.forbidden import ForbiddenIndex, LayerAMatch
from src.core.models import IngredientKind, MatchLayer


class TestForbiddenIndexLoading:
    """Tests for loading forbidden ingredients."""

    @pytest.fixture
    def sample_index(self, tmp_path):
        """Create a sample forbidden ingredients CSV."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text(
            "ingredient\n"
            "C6H6\n"
            "H2O2\n"
            "BHA\n"
            "Sodium Lauryl Sulfate\n"
            '"1,4-Dioxane"\n'
        )
        return ForbiddenIndex.from_csv(csv_path)

    def test_loads_all_entries(self, sample_index):
        """Test that all entries are loaded."""
        assert len(sample_index) == 5

    def test_classifies_formulas(self, sample_index):
        """Test that formulas are classified correctly."""
        assert sample_index.entries["C6H6"].kind == IngredientKind.FORMULA
        assert sample_index.entries["H2O2"].kind == IngredientKind.FORMULA

    def test_classifies_names(self, sample_index):
        """Test that names are classified correctly."""
        assert sample_index.entries["BHA"].kind == IngredientKind.NAME
        assert sample_index.entries["Sodium Lauryl Sulfate"].kind == IngredientKind.NAME
        assert sample_index.entries["1,4-Dioxane"].kind == IngredientKind.NAME


class TestLayerAMatching:
    """Tests for Layer A matching (combined exact + alias)."""

    @pytest.fixture
    def sample_index(self, tmp_path):
        """Create a sample forbidden ingredients CSV."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text(
            "ingredient\n"
            "C6H6\n"
            "BHA\n"
            "Sodium Lauryl Sulfate\n"
            '"1,4-Dioxane"\n'
        )
        return ForbiddenIndex.from_csv(csv_path)

    def test_exact_formula_match(self, sample_index):
        """Test exact formula matching."""
        result = sample_index.match_layer_a("C6H6")
        assert result is not None
        assert result.forbidden_raw == "C6H6"
        assert result.layer == MatchLayer.A_EXACT

    def test_exact_name_match(self, sample_index):
        """Test exact name matching."""
        result = sample_index.match_layer_a("BHA")
        assert result is not None
        assert result.forbidden_raw == "BHA"
        assert result.layer == MatchLayer.A_EXACT

        # Case insensitive
        result = sample_index.match_layer_a("bha")
        assert result is not None
        assert result.forbidden_raw == "BHA"

    def test_exact_multiword_match(self, sample_index):
        """Test exact multi-word matching."""
        result = sample_index.match_layer_a("Sodium Lauryl Sulfate")
        assert result is not None
        assert result.forbidden_raw == "Sodium Lauryl Sulfate"

        # Case insensitive
        result = sample_index.match_layer_a("sodium lauryl sulfate")
        assert result is not None
        assert result.forbidden_raw == "Sodium Lauryl Sulfate"

    def test_exact_special_char_match(self, sample_index):
        """Test exact matching with special characters."""
        result = sample_index.match_layer_a("1,4-Dioxane")
        assert result is not None
        assert result.forbidden_raw == "1,4-Dioxane"

        # Case insensitive
        result = sample_index.match_layer_a("1,4-dioxane")
        assert result is not None
        assert result.forbidden_raw == "1,4-Dioxane"

    def test_no_false_positives(self, sample_index):
        """Test that non-matches return None."""
        assert sample_index.match_layer_a("Benzene") is None  # Name, not formula
        assert sample_index.match_layer_a("Water") is None
        assert sample_index.match_layer_a("C6H12O6") is None  # Different formula


class TestAliasMatching:
    """Tests for alias/synonym matching after PubChem resolution."""

    @pytest.fixture
    def resolved_index(self, tmp_path):
        """Create a resolved index with mock synonyms."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text("ingredient\nC6H6\nH2O2\n")
        index = ForbiddenIndex.from_csv(csv_path)

        # Manually add synonyms (simulating PubChem resolution)
        index.entries["C6H6"].synonyms = ["Benzene", "Benzol", "Cyclohexatriene"]
        index.entries["H2O2"].synonyms = ["Hydrogen Peroxide", "Hydrogen dioxide"]

        # Build alias lookup (simulating what resolve_all does)
        for raw, entry in index.entries.items():
            for syn in entry.synonyms:
                norm_syn = syn.strip().lower()
                # Only add if not already present (preserve exact match priority)
                if norm_syn not in index._normalized_index:
                    index._normalized_index[norm_syn] = (raw, False)

        return index

    def test_alias_match_benzene_to_c6h6(self, resolved_index):
        """
        CRITICAL TEST: "Benzene" in product should match "C6H6" in forbidden list.
        """
        result = resolved_index.match_layer_a("Benzene")
        assert result is not None
        assert result.forbidden_raw == "C6H6"
        assert result.layer == MatchLayer.A_ALIAS

        result = resolved_index.match_layer_a("benzene")
        assert result is not None
        assert result.forbidden_raw == "C6H6"

    def test_alias_match_hydrogen_peroxide_to_h2o2(self, resolved_index):
        """
        CRITICAL TEST: "Hydrogen Peroxide" should match "H2O2" in forbidden list.
        """
        result = resolved_index.match_layer_a("Hydrogen Peroxide")
        assert result is not None
        assert result.forbidden_raw == "H2O2"
        assert result.layer == MatchLayer.A_ALIAS

        result = resolved_index.match_layer_a("hydrogen peroxide")
        assert result is not None
        assert result.forbidden_raw == "H2O2"

    def test_no_false_alias_matches(self, resolved_index):
        """Test that unrelated names don't match."""
        assert resolved_index.match_layer_a("Water") is None
        assert resolved_index.match_layer_a("Glucose") is None


class TestCIDMatching:
    """Tests for CID-based matching."""

    @pytest.fixture
    def resolved_index(self, tmp_path):
        """Create a resolved index with mock CIDs."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text("ingredient\nC6H6\nBHA\n")
        index = ForbiddenIndex.from_csv(csv_path)

        # Manually add CIDs (simulating PubChem resolution)
        index.entries["C6H6"].cids = [241]  # Benzene CID
        index.entries["BHA"].cids = [8456]  # BHA CID

        index.all_cids = {241, 8456}
        index.cid_to_entries = {
            241: ["C6H6"],
            8456: ["BHA"],
        }

        return index

    def test_cid_overlap_match(self, resolved_index):
        """Test CID overlap detection."""
        # If product ingredient resolves to CID 241, should match C6H6
        assert resolved_index.cid_overlap([241]) == "C6H6"
        assert resolved_index.cid_overlap([8456]) == "BHA"

    def test_cid_no_overlap(self, resolved_index):
        """Test no match when CIDs don't overlap."""
        assert resolved_index.cid_overlap([999, 1000, 1001]) is None

    def test_cid_multiple_overlap(self, resolved_index):
        """Test when ingredient has multiple CIDs."""
        # Should match the first overlapping one
        assert resolved_index.cid_overlap([999, 241, 8456]) == "C6H6"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
