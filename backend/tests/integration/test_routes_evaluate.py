"""Integration tests for POST /api/evaluate, hitting real sample fixtures
through the full HTTP stack (upload -> extraction -> parsing -> matching ->
decision), against the same hand-derived ledger used in
tests/unit/test_evaluation_against_samples.py.
"""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

_CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".txt": "text/plain"}


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_evaluate_all_30_samples_matches_the_ledger(
    client: TestClient, fixtures_dir: Path, expected_accepted_product_ids: set[str]
) -> None:
    with (fixtures_dir / "product_index.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 30

    for row in rows:
        path = fixtures_dir / row["filename"]
        content_type = _CONTENT_TYPES[path.suffix.lower()]
        with path.open("rb") as fh:
            response = client.post(
                "/api/evaluate", files={"files": (path.name, fh, content_type)}
            )

        assert response.status_code == 200, response.text
        body = response.json()
        is_accepted = row["product_id"] in expected_accepted_product_ids
        expected_status = "Accepted" if is_accepted else "Rejected"
        assert body["status"] == expected_status, f"{row['product_id']}: {body}"


def test_evaluate_matches_the_readme_contract_shape(client: TestClient, fixtures_dir: Path) -> None:
    path = fixtures_dir / "images" / "P-2025-0006_Pure_Lotion.png"
    with path.open("rb") as fh:
        response = client.post("/api/evaluate", files={"files": (path.name, fh, "image/png")})

    assert response.status_code == 200
    body = response.json()

    assert body["product_name"] == "Pure Lotion"
    assert body["status"] == "Rejected"
    assert body["reason"] == ["Contains Coumarin", "Contains Propylparaben"]
    match_keys = {"forbidden_ingredient", "matched_text", "method", "confidence"}
    assert match_keys <= body["matches"][0].keys()
    matched_ingredients = {m["forbidden_ingredient"] for m in body["matches"]}
    assert matched_ingredients == {"Coumarin", "Propylparaben"}


def test_evaluate_multi_row_csv_returns_the_batch_shape(client: TestClient) -> None:
    # A single multi-row CSV can't fit the single-object README contract, so
    # /evaluate falls back to the batch shape rather than erroring.
    csv_body = b"Product Name,Ingredients\nA,Water\nB,Coumarin\n"
    response = client.post(
        "/api/evaluate", files={"files": ("products.csv", csv_body, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    results = body["results"]
    assert len(results) == 2
    assert [r["result"]["product_name"] for r in results] == ["A", "B"]
    assert results[0]["result"]["status"] == "Accepted"
    assert results[1]["result"]["status"] == "Rejected"


def test_evaluate_accepts_a_single_row_csv(client: TestClient) -> None:
    csv_body = b"Product Name,Ingredients\nSynthetic Serum,Water;Glycerin\n"
    response = client.post(
        "/api/evaluate", files={"files": ("product.csv", csv_body, "text/csv")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["product_name"] == "Synthetic Serum"
    assert body["status"] == "Accepted"


def test_evaluate_unsupported_file_type_returns_415(client: TestClient) -> None:
    response = client.post(
        "/api/evaluate", files={"files": ("product.xyz", b"whatever", "application/octet-stream")}
    )

    assert response.status_code == 415


def test_evaluate_multiple_files_returns_the_batch_shape(
    client: TestClient, fixtures_dir: Path
) -> None:
    good_path = fixtures_dir / "images" / "P-2025-0006_Pure_Lotion.png"
    with good_path.open("rb") as good_fh:
        files = [
            ("files", (good_path.name, good_fh, "image/png")),
            ("files", ("bad.png", b"not actually a png", "image/png")),
        ]
        response = client.post("/api/evaluate", files=files)

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    results = body["results"]
    assert len(results) == 2

    good, bad = results
    assert good["status"] == "ok"
    assert good["result"]["product_name"] == "Pure Lotion"
    assert bad["status"] == "error"
    assert bad["result"] is None
    assert bad["error"]


def test_evaluate_two_good_files_of_different_types_both_succeed(
    client: TestClient, fixtures_dir: Path
) -> None:
    pdf_path = fixtures_dir / "pdfs" / "P-2025-0001_Pro_Moisturizer.pdf"
    text_path = fixtures_dir / "texts" / "P-2025-0024_Pro_Conditioner.txt"
    with pdf_path.open("rb") as pdf_fh, text_path.open("rb") as text_fh:
        files = [
            ("files", (pdf_path.name, pdf_fh, "application/pdf")),
            ("files", (text_path.name, text_fh, "text/plain")),
        ]
        response = client.post("/api/evaluate", files=files)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert all(item["status"] == "ok" for item in results)
    assert results[0]["result"]["product_name"] == "Pro Moisturizer"
    assert results[0]["result"]["status"] == "Rejected"
    assert results[1]["result"]["product_name"] == "Pro Conditioner"
    assert results[1]["result"]["status"] == "Accepted"


def test_evaluate_with_no_files_returns_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/evaluate", files=[])

    assert response.status_code == 422
