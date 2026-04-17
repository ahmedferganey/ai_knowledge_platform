from datetime import datetime

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_returns_200_with_correct_schema(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "api"
    assert payload["version"]
    assert datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
    assert set(payload) == {"status", "service", "version", "timestamp"}


def test_health_endpoint_requires_no_auth(client: TestClient) -> None:
    """Health endpoint must be reachable without any credentials."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_ready_endpoint_returns_readiness_schema(client: TestClient) -> None:
    """Readiness probe returns correct schema regardless of dependency state."""
    response = client.get("/api/v1/ready")

    assert response.status_code in (200, 503)
    payload = response.json()

    assert "status" in payload
    assert payload["status"] in ("ready", "not_ready")
    assert "timestamp" in payload
    assert datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))

    assert "checks" in payload
    checks = payload["checks"]
    assert "database" in checks
    assert "cache" in checks
    assert "vector_store" in checks
    for value in checks.values():
        assert value in ("ok", "degraded", "error")


def test_ready_endpoint_requires_no_auth(client: TestClient) -> None:
    """Readiness probe must be reachable without credentials (Kubernetes probe)."""
    response = client.get("/api/v1/ready")
    assert response.status_code in (200, 503)


def test_ready_endpoint_status_matches_http_code(client: TestClient) -> None:
    """When status is 'ready' HTTP is 200; when 'not_ready' HTTP is 503."""
    response = client.get("/api/v1/ready")
    payload = response.json()

    if payload["status"] == "ready":
        assert response.status_code == 200
    else:
        assert response.status_code == 503
