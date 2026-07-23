from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_evaluate_batch_isolates_a_bad_file_from_a_good_one(
    client: TestClient, fixtures_dir: Path
) -> None:
    good_path = fixtures_dir / "images" / "P-2025-0006_Pure_Lotion.png"
    with good_path.open("rb") as good_fh:
        files = [
            ("files", (good_path.name, good_fh, "image/png")),
            ("files", ("bad.png", b"not actually a png", "image/png")),
        ]
        response = client.post("/api/evaluate/batch", files=files)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2

    good, bad = results
    assert good["status"] == "ok"
    assert good["result"]["product_name"] == "Pure Lotion"
    assert bad["status"] == "error"
    assert bad["result"] is None
    assert bad["error"]


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
