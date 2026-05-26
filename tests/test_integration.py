"""
Integration tests for the Product Safety Compliance pipeline.

Tests end-to-end flow with mocked external dependencies (PubChem, OpenAI).
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Configure pytest-asyncio
pytestmark = pytest.mark.anyio

from src.core.matching.forbidden import ForbiddenIndex
from src.core.matching.pipeline import MatchPipeline
from src.core.matching.pubchem import PubChemClient
from src.core.models import ProductExtraction, ProductStatus, MatchLayer


class TestPipelineIntegration:
    """End-to-end integration tests with mocked dependencies."""

    @pytest.fixture
    def forbidden_index(self, tmp_path):
        """Create a forbidden index with pre-resolved data."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text(
            "ingredient\n"
            "C6H6\n"
            "H2O2\n"
            "Formaldehyde\n"
        )
        index = ForbiddenIndex.from_csv(csv_path)

        # Manually resolve (simulating PubChem)
        # C6H6 (Benzene)
        index.entries["C6H6"].cids = [241]
        index.entries["C6H6"].synonyms = ["Benzene", "Benzol"]

        # H2O2 (Hydrogen Peroxide)
        index.entries["H2O2"].cids = [784]
        index.entries["H2O2"].synonyms = ["Hydrogen Peroxide", "Hydrogen dioxide"]

        # Formaldehyde
        index.entries["Formaldehyde"].cids = [712]
        index.entries["Formaldehyde"].synonyms = ["Methanal", "Formalin"]

        # Build indexes
        for raw, entry in index.entries.items():
            for cid in entry.cids:
                index.all_cids.add(cid)
                if cid not in index.cid_to_entries:
                    index.cid_to_entries[cid] = []
                index.cid_to_entries[cid].append(raw)

            for syn in entry.synonyms:
                norm_syn = syn.strip().lower()
                if norm_syn not in index._normalized_index:
                    index._normalized_index[norm_syn] = (raw, False)

        return index

    @pytest.fixture
    def mock_pubchem(self):
        """Create a mock PubChem client."""
        client = PubChemClient()
        # Pre-populate cache so no real API calls happen
        client._cid_cache = {
            "name:water": [962],
            "name:glycerin": [753],
            "name:citric acid": [311],
            "name:unknown compound": [],
            "name:ethanol": [702],
            "name:isopropyl alcohol": [3776],
            "name:ammonia": [222],
        }
        return client

    @pytest.fixture
    def pipeline(self, forbidden_index, mock_pubchem):
        """Create a pipeline with mocked dependencies."""
        return MatchPipeline(forbidden_index, mock_pubchem)

    async def test_accepted_product_no_forbidden(self, pipeline):
        """Test that a product with no forbidden ingredients is accepted."""
        # Mock LLM judge to return no matches
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P001",
                product_name="Safe Lotion",
                ingredients=["Water", "Glycerin", "Citric Acid"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "safe_lotion.txt")

            assert result.status == ProductStatus.ACCEPTED
            assert len(result.hits) == 0
            assert result.reason == []

    async def test_rejected_product_exact_formula_match(self, pipeline):
        """Test that a product with exact formula match is rejected."""
        # Mock LLM judge (shouldn't be called for exact matches)
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P002",
                product_name="Dangerous Solvent",
                ingredients=["Water", "C6H6", "Ethanol"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "dangerous_solvent.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.hits) == 1
            assert result.hits[0].ingredient == "C6H6"
            assert result.hits[0].forbidden_match == "C6H6"
            assert result.hits[0].layer == MatchLayer.A_EXACT

    async def test_rejected_product_alias_match(self, pipeline):
        """
        CRITICAL TEST: Product with "Benzene" should be rejected
        because it matches "C6H6" in forbidden list via alias.
        """
        # Mock LLM judge (shouldn't be called for alias matches)
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P003",
                product_name="Industrial Cleaner",
                ingredients=["Water", "Benzene", "Isopropyl Alcohol"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "cleaner.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.hits) == 1
            assert result.hits[0].ingredient == "Benzene"
            assert result.hits[0].forbidden_match == "C6H6"
            assert result.hits[0].layer == MatchLayer.A_ALIAS

    async def test_rejected_product_hydrogen_peroxide_match(self, pipeline):
        """
        CRITICAL TEST: "Hydrogen Peroxide" should match "H2O2".
        """
        # Mock LLM judge (shouldn't be called for alias matches)
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P004",
                product_name="Hair Bleach",
                ingredients=["Water", "Hydrogen Peroxide", "Ammonia"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "hair_bleach.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.hits) == 1
            assert result.hits[0].ingredient == "Hydrogen Peroxide"
            assert result.hits[0].forbidden_match == "H2O2"

    async def test_rejected_product_multiple_matches(self, pipeline):
        """Test product with multiple forbidden ingredients."""
        # Mock LLM judge (shouldn't be called for alias matches)
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P005",
                product_name="Very Bad Product",
                ingredients=["Benzene", "Hydrogen Peroxide", "Formaldehyde"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "very_bad.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.hits) == 3

            # Verify all matches found
            matched_ingredients = {h.ingredient for h in result.hits}
            assert "Benzene" in matched_ingredients
            assert "Hydrogen Peroxide" in matched_ingredients
            assert "Formaldehyde" in matched_ingredients

    async def test_reason_format(self, pipeline):
        """Test that reason strings follow the expected format."""
        # Mock LLM judge
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P006",
                product_name="Test Product",
                ingredients=["Benzene"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "test.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.reason) == 1
            assert "Contains Benzene" in result.reason[0]
            assert "matches C6H6" in result.reason[0]

    async def test_trace_records_layer_a_hits(self, pipeline):
        """Test that trace correctly records Layer A statistics."""
        # Mock LLM judge
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P007",
                product_name="Mixed Product",
                ingredients=["Water", "Benzene", "Glycerin"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "mixed.txt")

            # 3 ingredients checked in Layer A
            assert result.trace.layer_a_checks == 3
            # 1 hit (Benzene)
            assert result.trace.layer_a_hits == 1
            # 2 went to Layer B (Water, Glycerin - no match)
            assert result.trace.layer_b_checks == 2


class TestLayerBIntegration:
    """Integration tests for Layer B (CID matching)."""

    @pytest.fixture
    def forbidden_index(self, tmp_path):
        """Create a forbidden index."""
        csv_path = tmp_path / "forbidden.csv"
        csv_path.write_text("ingredient\nC6H6\n")
        index = ForbiddenIndex.from_csv(csv_path)

        # Set up CID for Benzene
        index.entries["C6H6"].cids = [241]
        index.all_cids = {241}
        index.cid_to_entries = {241: ["C6H6"]}

        return index

    @pytest.fixture
    def mock_pubchem_with_cid(self):
        """Create a mock PubChem that returns CIDs."""
        client = PubChemClient()
        # Simulate that "Some Chemical" resolves to same CID as Benzene
        client._cid_cache = {
            "name:some chemical": [241],  # Same CID as Benzene!
        }
        return client

    @pytest.fixture
    def pipeline(self, forbidden_index, mock_pubchem_with_cid):
        """Create pipeline with CID-aware mock."""
        return MatchPipeline(forbidden_index, mock_pubchem_with_cid)

    async def test_layer_b_cid_match(self, pipeline):
        """Test that Layer B matches via CID overlap."""
        # Mock LLM judge
        with patch('src.core.matching.pipeline.judge_ingredients', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = []

            extraction = ProductExtraction(
                product_id="P008",
                product_name="Mystery Product",
                ingredients=["Some Chemical"],
                extraction_method="text",
            )

            result = await pipeline.evaluate(extraction, "mystery.txt")

            assert result.status == ProductStatus.REJECTED
            assert len(result.hits) == 1
            assert result.hits[0].layer == MatchLayer.B_PUBCHEM
            assert result.hits[0].cid == 241


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
