import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_evaluate_batch_samples_matches_the_ledger_against_the_real_dataset(
    client: TestClient, expected_accepted_product_ids: set[str]
) -> None:
    response = client.post("/api/evaluate/batch-samples")

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 30
    assert all(item["status"] == "ok" for item in results)

    for item in results:
        is_accepted = item["product_id"] in expected_accepted_product_ids
        expected_status = "Accepted" if is_accepted else "Rejected"
        assert item["result"]["status"] == expected_status, item
