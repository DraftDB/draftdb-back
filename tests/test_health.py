from sqlalchemy.exc import OperationalError
from app.database import get_db
from app.main import app


def test_health_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_base_indisponible(client):
    class SessionEnPanne:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connexion refusée"))

    app.dependency_overrides[get_db] = lambda: SessionEnPanne()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "indisponible"}


def test_swagger_sous_le_prefixe_api(client):
    assert client.get("/api/docs").status_code == 200

    chemins = client.get("/api/openapi.json").json()["paths"]
    assert "/api/health" in chemins