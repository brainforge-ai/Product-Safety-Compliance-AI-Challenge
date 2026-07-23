from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_products_history_is_always_empty_when_persistence_disabled(
    monkeypatch, fixtures_dir: Path
) -> None:
    monkeypatch.setenv("ENABLE_PERSISTENCE", "false")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            path = fixtures_dir / "images" / "P-2025-0006_Pure_Lotion.png"
            with path.open("rb") as fh:
                client.post("/api/evaluate", files={"file": (path.name, fh, "image/png")})

            response = client.get("/api/products")
            assert response.status_code == 200
            assert response.json() == {"items": [], "limit": 50, "offset": 0}
    finally:
        get_settings.cache_clear()


def test_products_history_records_evaluations_when_persistence_enabled(
    tmp_path, monkeypatch, fixtures_dir: Path
) -> None:
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("ENABLE_PERSISTENCE", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            path = fixtures_dir / "images" / "P-2025-0006_Pure_Lotion.png"
            with path.open("rb") as fh:
                client.post("/api/evaluate", files={"file": (path.name, fh, "image/png")})

            response = client.get("/api/products")
            assert response.status_code == 200
            body = response.json()
            assert body["limit"] == 50
            assert body["offset"] == 0
            [item] = body["items"]
            assert item["product_id"] == "P-2025-0006"
            assert item["result"]["product_name"] == "Pure Lotion"
    finally:
        get_settings.cache_clear()


def test_batch_samples_persists_all_30_evaluations(tmp_path, monkeypatch) -> None:
    """Cross-cutting case not covered elsewhere: 30 concurrently-evaluated
    products, all writing to the same request-scoped SQLite session.
    """
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("ENABLE_PERSISTENCE", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            batch_response = client.post("/api/evaluate/batch-samples")
            assert batch_response.status_code == 200
            assert len(batch_response.json()["results"]) == 30

            history = client.get("/api/products", params={"limit": 100})
            assert history.status_code == 200
            items = history.json()["items"]
            assert len(items) == 30
            assert len({item["product_id"] for item in items}) == 30
    finally:
        get_settings.cache_clear()
