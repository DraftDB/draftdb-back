import pytest
from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app


class FakeSession:
    """Session factice : permet de tester sans base PostgreSQL."""

    def execute(self, *args, **kwargs):
        return None


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: FakeSession()
    yield TestClient(app)
    app.dependency_overrides.clear()