from fastapi.testclient import  TestClient
from app.main import app

def test_health_endpoint_returns_service_metadata() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "living-rag-api"
    assert "timestamp" in payload