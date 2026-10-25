def test_health_endpoint(client):
    """Test that GET /health returns 200 with service health status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "vani-2.0-poc"
    assert data["stage"] == "1"
