"""Vérifie que l'API démarre et répond."""

from fastapi.testclient import TestClient

from backend.main import application


def test_health_endpoint_reports_ok() -> None:
    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
