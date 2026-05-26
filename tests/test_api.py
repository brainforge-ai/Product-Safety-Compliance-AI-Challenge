"""
HTTP endpoint smoke tests for the FastAPI application.

Uses TestClient for synchronous testing of async endpoints.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.core.models import (
    EvaluationResult,
    ProductStatus,
    MatchTrace,
)


@pytest.fixture
def mock_pipeline():
    """Mock the global pipeline initialization."""
    with patch('src.api.main.create_pipeline', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = AsyncMock()
        yield mock_create.return_value


@pytest.fixture
def client(mock_pipeline):
    """Create a test client with mocked pipeline."""
    # Import app after mocking to avoid startup initialization
    from src.api.main import app

    # Manually set the pipeline
    import src.api.main as api_module
    api_module.pipeline = mock_pipeline

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_ok(self, client):
        """Test that health endpoint returns 200."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["pipeline_ready"] is True


class TestEvaluateProductEndpoint:
    """Smoke tests for POST /evaluate_product."""

    def test_evaluate_txt_file(self, client, tmp_path):
        """Test evaluating a simple text file."""
        # Create a test product file
        product_file = tmp_path / "test_product.txt"
        product_file.write_text(
            "Product: Test Lotion\n"
            "Ingredients: Water, Glycerin, Citric Acid"
        )

        # Mock evaluate_file to return a valid result
        mock_result = EvaluationResult(
            product_id=None,
            product_name="Test Lotion",
            filename="test_product.txt",
            status=ProductStatus.ACCEPTED,
            reason=[],
            hits=[],
            ingredients_detected=["Water", "Glycerin", "Citric Acid"],
            trace=MatchTrace(),
            extraction_method="text",
            duration_ms=100.0,
        )

        with patch('src.api.main.evaluate_file', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = mock_result

            with open(product_file, "rb") as f:
                response = client.post(
                    "/evaluate_product",
                    files={"file": ("test_product.txt", f, "text/plain")},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Accepted"
        assert data["product_name"] == "Test Lotion"

    def test_evaluate_missing_file_returns_422(self, client):
        """Test that missing file returns 422."""
        response = client.post("/evaluate_product")

        assert response.status_code == 422

    def test_evaluate_rejected_product(self, client, tmp_path):
        """Test that rejected products return proper status."""
        product_file = tmp_path / "bad_product.txt"
        product_file.write_text(
            "Product: Bad Cleaner\n"
            "Ingredients: Water, Benzene, Ethanol"
        )

        mock_result = EvaluationResult(
            product_id=None,
            product_name="Bad Cleaner",
            filename="bad_product.txt",
            status=ProductStatus.REJECTED,
            reason=["Contains Benzene (matches C6H6)"],
            hits=[],
            ingredients_detected=["Water", "Benzene", "Ethanol"],
            trace=MatchTrace(),
            extraction_method="text",
            duration_ms=150.0,
        )

        with patch('src.api.main.evaluate_file', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = mock_result

            with open(product_file, "rb") as f:
                response = client.post(
                    "/evaluate_product",
                    files={"file": ("bad_product.txt", f, "text/plain")},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Rejected"
        assert len(data["reason"]) == 1
        assert "Benzene" in data["reason"][0]


class TestEvaluateByPathEndpoint:
    """Smoke tests for POST /evaluate/path."""

    def test_evaluate_by_path_file_not_found(self, client):
        """Test that non-existent file returns 404."""
        response = client.post(
            "/evaluate/path",
            json={"file_path": "/nonexistent/file.txt"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_evaluate_by_path_success(self, client, tmp_path):
        """Test evaluating a file by path."""
        product_file = tmp_path / "product.txt"
        product_file.write_text("Product: Test\nIngredients: Water")

        mock_result = EvaluationResult(
            product_id=None,
            product_name="Test",
            filename="product.txt",
            status=ProductStatus.ACCEPTED,
            reason=[],
            hits=[],
            ingredients_detected=["Water"],
            trace=MatchTrace(),
            extraction_method="text",
            duration_ms=50.0,
        )

        with patch('src.api.main.evaluate_file', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = mock_result

            response = client.post(
                "/evaluate/path",
                json={"file_path": str(product_file)},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Accepted"
