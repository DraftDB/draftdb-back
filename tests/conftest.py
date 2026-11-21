from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db, get_engine
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


@pytest.fixture
def db_session():
    """Vraie session PostgreSQL dans une transaction annulée à la fin du test (rien ne reste en base)."""
    try:
        connexion = get_engine().connect()
    except (OperationalError, ValidationError):
        pytest.skip("Base PostgreSQL indisponible : lancer docker compose up -d et créer le .env")
    transaction = connexion.begin()
    session = Session(bind=connexion, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connexion.close()


@pytest.fixture
def client_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def monde(db_session):
    """Trois utilisateurs et un projet : responsable, relecteur participant, étranger au projet."""
    ids = {nom: uuid4() for nom in ("responsable", "relecteur", "etranger", "projet")}
    for nom in ("responsable", "relecteur", "etranger"):
        db_session.execute(
            text("INSERT INTO utilisateur (id_utilisateur, login, empreinte_mdp) VALUES (:id, :login, 'x')"),
            {"id": ids[nom], "login": f"{nom}-{ids[nom]}"[:50]},
        )
    db_session.execute(
        text("INSERT INTO projet (id_projet, nom, id_responsable) VALUES (:p, 'Projet', :r)"),
        {"p": ids["projet"], "r": ids["responsable"]},
    )
    db_session.execute(
        text("INSERT INTO participation (id_utilisateur, id_projet, est_concepteur, est_relecteur) VALUES (:u, :p, true, false)"),
        {"u": ids["responsable"], "p": ids["projet"]},
    )
    db_session.execute(
        text("INSERT INTO participation (id_utilisateur, id_projet, est_concepteur, est_relecteur) VALUES (:u, :p, false, true)"),
        {"u": ids["relecteur"], "p": ids["projet"]},
    )
    db_session.flush()
    return ids


def en_tete(id_utilisateur) -> dict:
    return {"X-User-Id": str(id_utilisateur)}


# Les identifiants ChartDB sont des clés primaires globales en base : pour que les tests ne
# collisionnent jamais avec des données déjà présentes (import manuel, seed...), chaque
# exécution de pytest utilise un suffixe aléatoire. i("t_client") donne par exemple "t_client_a1b2c3".
SUFFIXE = uuid4().hex[:6]


def i(base: str) -> str:
    return f"{base}_{SUFFIXE}"


def _diagramme() -> dict:
    return {
        "id": i("diag1"),
        "name": "Boutique",
        "databaseType": "postgresql",
        "tables": [
            {
                "id": i("t_client"), "name": "client", "x": 10, "y": 20, "color": "#8eb7ff", "isView": False,
                "createdAt": 1700000000000,
                "fields": [
                    {"id": i("c_client_id"), "name": "id", "type": {"id": "integer", "name": "integer"},
                     "primaryKey": True, "unique": True, "nullable": False, "increment": True, "createdAt": 1700000000000},
                    {"id": i("c_client_nom"), "name": "nom", "type": {"id": "varchar", "name": "varchar"},
                     "primaryKey": False, "unique": False, "nullable": False, "characterMaximumLength": "100",
                     "createdAt": 1700000000000},
                ],
                "indexes": [{"id": i("i_client_pk"), "name": "client_pkey", "unique": True, "fieldIds": [i("c_client_id")],
                             "isPrimaryKey": True, "createdAt": 1700000000000}],
            },
            {
                "id": i("t_commande"), "name": "commande", "x": 300, "y": 20, "color": "#ffb3ba", "isView": False,
                "createdAt": 1700000000000,
                "fields": [
                    {"id": i("c_cmd_id"), "name": "id", "type": {"id": "integer", "name": "integer"},
                     "primaryKey": True, "unique": True, "nullable": False, "createdAt": 1700000000000},
                    {"id": i("c_cmd_client"), "name": "client_id", "type": {"id": "integer", "name": "integer"},
                     "primaryKey": False, "unique": False, "nullable": False, "createdAt": 1700000000000},
                ],
                "indexes": [],
            },
        ],
        "relationships": [
            {"id": i("r_cmd_client"), "name": "fk_commande_client", "sourceTableId": i("t_commande"),
             "targetTableId": i("t_client"), "sourceFieldId": i("c_cmd_client"), "targetFieldId": i("c_client_id"),
             "sourceCardinality": "many", "targetCardinality": "one", "createdAt": 1700000000000},
        ],
        "areas": [{"id": i("a1"), "name": "Zone clients", "x": 0, "y": 0, "width": 200, "height": 200, "color": "#fff"}],
        "notes": [], "customTypes": [], "dependencies": [],
    }


def diagramme_autre() -> dict:
    """Un second diagramme, aux identifiants différents (pour tester le remplacement)."""
    return {
        "id": i("diag2"), "name": "Autre",
        "tables": [{
            "id": i("t_autre"), "name": "autre",
            "fields": [{"id": i("c_autre_id"), "name": "id", "type": {"id": "uuid"}, "primaryKey": True, "nullable": False}],
        }],
    }


def diagramme_exemple(**remplacements) -> dict:
    d = _diagramme()
    d.update(remplacements)
    return d


def corps_import(diagramme: dict | None = None, **remplacements) -> dict:
    corps = {
        "confirme_remplacement": False,
        "fichier": {"nom": "dump.sql", "dialecte": "postgresql", "taille_octets": 2048},
        "diagramme": diagramme or diagramme_exemple(),
        "rapport": {"non_repris": [{"ligne": 42, "type": "INSERT", "raison": "instruction de données"}]},
    }
    corps.update(remplacements)
    return corps