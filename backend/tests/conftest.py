import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.session_store import get_session_store


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure in-memory session store is cleared before each test."""
    store = get_session_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)
