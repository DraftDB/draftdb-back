"""Tests de l'ouverture d'un projet (CU 1.6) contre la vraie base PostgreSQL."""

import pytest

from tests.conftest import corps_import, diagramme_autre, diagramme_exemple, en_tete, i

pytestmark = pytest.mark.integration


def _ouvrir(client, monde, utilisateur="responsable"):
    return client.get(f"/api/projets/{monde['projet']}", headers=en_tete(monde[utilisateur]))


def test_projet_vide(client_db, monde):
    reponse = _ouvrir(client_db, monde)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["nom"] == "Projet" and corps["type_base"] == "generic"
    assert corps["diagramme"]["tables"] == [] and corps["diagramme"]["databaseType"] == "generic"


def test_relit_ce_que_l_import_a_ecrit(client_db, monde):
    client_db.post(f"/api/projets/{monde['projet']}/import", json=corps_import(), headers=en_tete(monde["responsable"]))

    diagramme = _ouvrir(client_db, monde).json()["diagramme"]

    attendu = diagramme_exemple()
    assert diagramme["databaseType"] == "postgresql"
    assert {t["id"] for t in diagramme["tables"]} == {i("t_client"), i("t_commande")}
    client = next(t for t in diagramme["tables"] if t["id"] == i("t_client"))
    assert [f["id"] for f in client["fields"]] == [i("c_client_id"), i("c_client_nom")]  # ordre (rang) conservé
    assert client["fields"][1]["characterMaximumLength"] == "100"
    assert client["fields"][0]["primaryKey"] is True and client["fields"][0]["increment"] is True
    assert client["indexes"][0]["fieldIds"] == [i("c_client_id")]
    rel = diagramme["relationships"][0]
    assert (rel["sourceTableId"], rel["targetTableId"]) == (i("t_commande"), i("t_client"))
    assert (rel["sourceCardinality"], rel["targetCardinality"]) == ("many", "one")
    assert diagramme["areas"] == attendu["areas"]


def test_les_elements_supprimes_ne_sont_pas_renvoyes(client_db, monde):
    h = en_tete(monde["responsable"])
    client_db.post(f"/api/projets/{monde['projet']}/import", json=corps_import(), headers=h)
    client_db.post(f"/api/projets/{monde['projet']}/import",
                   json=corps_import(diagramme_autre(), confirme_remplacement=True), headers=h)

    diagramme = _ouvrir(client_db, monde).json()["diagramme"]

    assert [t["id"] for t in diagramme["tables"]] == [i("t_autre")]
    assert diagramme["relationships"] == []


def test_un_participant_non_responsable_peut_ouvrir(client_db, monde):
    assert _ouvrir(client_db, monde, utilisateur="relecteur").status_code == 200


def test_refus_si_non_participant(client_db, monde):
    assert _ouvrir(client_db, monde, utilisateur="etranger").status_code == 403


def test_projet_inconnu(client_db, monde):
    from uuid import uuid4

    reponse = client_db.get(f"/api/projets/{uuid4()}", headers=en_tete(monde["responsable"]))
    assert reponse.status_code == 404