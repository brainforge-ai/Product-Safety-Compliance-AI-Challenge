import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_get_forbidden_ingredients_returns_the_default_list(client: TestClient) -> None:
    response = client.get("/api/forbidden-ingredients")

    assert response.status_code == 200
    ingredients = response.json()["ingredients"]
    assert len(ingredients) == 13
    assert "Coumarin" in ingredients
    assert "1,4-Dioxane" in ingredients


def test_post_forbidden_ingredients_replaces_the_active_list(client: TestClient) -> None:
    csv_body = b"ingredient\nWater\nSand\n"
    response = client.post(
        "/api/forbidden-ingredients", files={"file": ("list.csv", csv_body, "text/csv")}
    )

    assert response.status_code == 200
    assert response.json()["ingredients"] == ["Water", "Sand"]

    follow_up = client.get("/api/forbidden-ingredients")
    assert follow_up.json()["ingredients"] == ["Water", "Sand"]


def test_post_forbidden_ingredients_rejects_an_empty_csv(client: TestClient) -> None:
    response = client.post(
        "/api/forbidden-ingredients",
        files={"file": ("empty.csv", b"ingredient\n", "text/csv")},
    )

    assert response.status_code == 422


def test_post_forbidden_ingredients_rejects_non_utf8_bytes(client: TestClient) -> None:
    response = client.post(
        "/api/forbidden-ingredients",
        files={"file": ("bad.csv", b"\xff\xfe\x00\x01", "text/csv")},
    )

    assert response.status_code == 422
