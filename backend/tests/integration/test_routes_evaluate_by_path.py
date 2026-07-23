import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_evaluate_by_path_evaluates_a_real_sample(client: TestClient) -> None:
    response = client.post(
        "/api/evaluate/by-path",
        json={"path": "pdfs/P-2025-0001_Pro_Moisturizer.pdf"},
    )

    assert response.status_code == 200
    assert response.json()["product_name"] == "Pro Moisturizer"


def test_evaluate_by_path_rejects_traversal_outside_sample_data_dir(client: TestClient) -> None:
    response = client.post(
        "/api/evaluate/by-path",
        json={"path": "../../../etc/passwd"},
    )

    assert response.status_code == 400


def test_evaluate_by_path_returns_404_for_a_missing_file(client: TestClient) -> None:
    response = client.post(
        "/api/evaluate/by-path",
        json={"path": "pdfs/does_not_exist.pdf"},
    )

    assert response.status_code == 404
