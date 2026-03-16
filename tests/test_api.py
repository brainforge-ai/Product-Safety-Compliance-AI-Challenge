import io
import os

os.environ.setdefault("PRELOAD_MODELS", "0")
os.environ.setdefault("PRELOAD_OCR", "0")
os.environ.setdefault("ENABLE_PUBCHEM_SYNONYMS", "0")

import app.main as main_module
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _ensure_ready_state():
    main_module._ensure_app_state(app)
    if not app.state.startup_complete:
        main_module._warmup_dependencies(app)


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_ready():
    _ensure_ready_state()
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["startup_complete"] is True


def test_root_removed():
    response = client.get("/")
    assert response.status_code == 404


def test_evaluate_product_rejects_plain_text_forbidden_list():
    payload = b"Ingredients: Water, Glycerin, Methylparaben\nProduct Name: Test Lotion"
    response = client.post(
        "/evaluate_product",
        files={"file": ("label.txt", io.BytesIO(payload), "text/plain")},
        data={"forbidden_list": "methylparaben"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Rejected"
    assert "Contains Methylparaben" in body["reason"]
    assert "request_id" in body


def test_evaluate_product_requires_forbidden_list():
    payload = b"Ingredients: Water, Glycerin, Methylparaben\nProduct Name: Test Lotion"
    response = client.post(
        "/evaluate_product",
        files={"file": ("label.txt", io.BytesIO(payload), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "forbidden_list is required and must be provided in the request"


def test_evaluate_product_path_missing_file():
    response = client.post(
        "/evaluate_product_path",
        data={"path": "samples/does-not-exist.txt", "forbidden_list": "methylparaben"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_evaluate_products_batch():
    response = client.post(
        "/evaluate_products",
        files=[
            ("files", ("a.txt", io.BytesIO(b"Ingredients: Water, Methylparaben"), "text/plain")),
            ("files", ("b.txt", io.BytesIO(b"Ingredients: Water, Glycerin"), "text/plain")),
        ],
        data={"forbidden_list": "methylparaben"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["status"] == "Rejected"
    assert body["results"][1]["status"] == "Accepted"
    assert "request_id" in body


def test_evaluate_product_rejects_oversized_request():
    previous = main_module.MAX_UPLOAD_SIZE_BYTES
    main_module.MAX_UPLOAD_SIZE_BYTES = 10
    try:
        response = client.post(
            "/evaluate_product",
            files={"file": ("big.txt", io.BytesIO(b"0123456789abcdef"), "text/plain")},
            data={"forbidden_list": "methylparaben"},
        )
        assert response.status_code == 413
    finally:
        main_module.MAX_UPLOAD_SIZE_BYTES = previous