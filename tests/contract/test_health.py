from datetime import datetime

from fastapi.testclient import TestClient


def test_health_endpoint_returns_contract_shape(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "api"
    assert payload["version"]
    assert datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
    assert set(payload) == {"status", "service", "version", "timestamp"}
