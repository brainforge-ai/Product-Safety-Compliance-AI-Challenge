from fastapi.testclient import TestClient

from app.main import app


def test_swagger_ui_is_served() -> None:
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_openapi_schema_is_served() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Product Safety Compliance AI System"
    assert "/api/health" in schema["paths"]
