def test_skills_endpoint_returns_supported_skills(client):
    """Test that GET /api/skills returns the 4 predefined skills."""
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)
    expected = ["Python", "SQL", "Java", "Machine Learning"]
    assert data["skills"] == expected
