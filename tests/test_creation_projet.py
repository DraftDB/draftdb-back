"""Tests de la création d'un projet (CU 1.1) contre la vraie base PostgreSQL."""
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.conftest import en_tete

pytestmark = pytest.mark.integration


def _creer(client, monde, corps, utilisateur="responsable"):
    return client.post("/api/projets", json=corps, headers=en_tete(monde[utilisateur]))


def _compter(db, table):
    return db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def _ecrit_par_la_creation(db, id_utilisateur):
    """Ce que CU 1.1 a écrit pour cet utilisateur, hors projet 'Projet' de la fixture.

    On filtre sur l'utilisateur du test : la base peut contenir d'autres données (seed, tests manuels).
    Le rollback de la route annule aussi la fixture, qui partage sa session : on ne peut donc pas
    comparer des totaux avant/après.
    """
    u = {"u": id_utilisateur}
    return (
        db.execute(text("SELECT count(*) FROM projet WHERE id_responsable = :u AND nom <> 'Projet'"), u).scalar_one(),
        db.execute(text("SELECT count(*) FROM participation pa JOIN projet p USING (id_projet) "
                        "WHERE pa.id_utilisateur = :u AND p.nom <> 'Projet'"), u).scalar_one(),
        db.execute(text("SELECT count(*) FROM evenement_journal WHERE nature = 'CREATION_PROJET' AND id_utilisateur = :u"), u).scalar_one(),
    )


def test_creation_nominale(client_db, monde, db_session):
    r = _creer(client_db, monde, {"nom": "Boutique", "description": "Schéma de la boutique"})
    assert r.status_code == 201
    c = r.json()
    assert set(c) == {"id_projet", "nom", "description", "type_base", "numero_sequence"}
    assert (c["nom"], c["description"], c["type_base"], c["numero_sequence"]) == ("Boutique", "Schéma de la boutique", "generic", 0)

    p = db_session.execute(text("SELECT * FROM projet WHERE id_projet = :i"), {"i": c["id_projet"]}).mappings().one()
    assert p["id_responsable"] == monde["responsable"] and p["annexes"] == {}
    part = db_session.execute(text("SELECT * FROM participation WHERE id_projet = :i"), {"i": c["id_projet"]}).mappings().all()
    assert len(part) == 1 and part[0]["id_utilisateur"] == monde["responsable"]
    assert part[0]["est_concepteur"] is True and part[0]["est_relecteur"] is False
    j = db_session.execute(text("SELECT * FROM evenement_journal WHERE id_projet = :i"), {"i": c["id_projet"]}).mappings().all()
    assert len(j) == 1 and j[0]["nature"] == "CREATION_PROJET" and j[0]["id_utilisateur"] == monde["responsable"]
    assert j[0]["details"] == {"nom": "Boutique"}
    assert db_session.execute(text("SELECT count(*) FROM element_schema WHERE id_projet = :i"), {"i": c["id_projet"]}).scalar_one() == 0
    assert db_session.execute(text("SELECT count(*) FROM operation WHERE id_projet = :i"), {"i": c["id_projet"]}).scalar_one() == 0


def test_description_facultative(client_db, monde):
    assert _creer(client_db, monde, {"nom": "Sans description"}).json()["description"] is None
    assert _creer(client_db, monde, {"nom": "Vide", "description": "  "}).json()["description"] is None


def test_nom_nettoye_et_limites_acceptees(client_db, monde):
    assert _creer(client_db, monde, {"nom": "  Boutique  "}).json()["nom"] == "Boutique"
    assert _creer(client_db, monde, {"nom": "n" * 100, "description": "d" * 500}).status_code == 201


def test_projet_ouvrable_par_son_createur(client_db, monde):
    id_projet = _creer(client_db, monde, {"nom": "Ouvrable"}).json()["id_projet"]
    r = client_db.get(f"/api/projets/{id_projet}", headers=en_tete(monde["responsable"]))
    assert r.status_code == 200 and r.json()["diagramme"]["tables"] == []
    # EX-08 : un non-participant ne voit pas le projet
    assert client_db.get(f"/api/projets/{id_projet}", headers=en_tete(monde["etranger"])).status_code == 403


def test_deux_projets_de_meme_nom(client_db, monde):
    a = _creer(client_db, monde, {"nom": "Doublon"})
    b = _creer(client_db, monde, {"nom": "Doublon"})
    assert a.status_code == 201 and b.status_code == 422


@pytest.mark.parametrize("en_tetes", [{}, {"X-User-Id": "pas-un-uuid"}, {"X-User-Id": str(uuid4())}])
def test_401_et_rien_cree(client_db, db_session, en_tetes):
    avant = _compter(db_session, "projet")
    assert client_db.post("/api/projets", json={"nom": "X"}, headers=en_tetes).status_code == 401
    assert _compter(db_session, "projet") == avant


def test_401_prioritaire_sur_422(client_db):
    assert client_db.post("/api/projets", json={}).status_code == 401


@pytest.mark.parametrize("corps", [
    {}, {"description": "x"}, {"nom": ""}, {"nom": "   "}, {"nom": None}, {"nom": "n" * 101},
    {"nom": "ok", "description": "d" * 501}, {"nom": 12},
])
def test_422_et_rien_cree(client_db, monde, db_session, corps):
    avant = [_compter(db_session, t) for t in ("projet", "participation", "evenement_journal")]
    r = _creer(client_db, monde, corps)
    assert r.status_code == 422 and isinstance(r.json()["detail"], list)
    assert [_compter(db_session, t) for t in ("projet", "participation", "evenement_journal")] == avant


@pytest.mark.parametrize("corps", [{"nom": "a\x00b"}, {"nom": "ok", "description": "a\x00b"}])
def test_nul_refuse_par_la_base_422_rollback(client_db, monde, db_session, corps):
    r = _creer(client_db, monde, corps)
    assert r.status_code == 422
    assert _ecrit_par_la_creation(db_session, monde["responsable"]) == (0, 0, 0)


def test_atomicite_si_le_journal_echoue(client_db, monde, db_session, monkeypatch):
    """Si une écriture échoue en cours de route, rien n'est enregistré (une seule transaction)."""
    from app.services import projets as svc
    def casse(*a, **k):
        raise svc.DataError("INSERT", {}, Exception("boom"))
    monkeypatch.setattr(svc, "bindparam", casse)
    assert _creer(client_db, monde, {"nom": "Atomique"}).status_code == 422
    assert _ecrit_par_la_creation(db_session, monde["responsable"]) == (0, 0, 0)


def test_swagger_expose_la_route(client_db):
    chemins = client_db.get("/api/openapi.json").json()["paths"]
    assert "post" in chemins["/api/projets"]
