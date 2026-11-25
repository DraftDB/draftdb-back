"""Tests de la route d'import (CU 1.5) contre la vraie base PostgreSQL."""

import pytest
from sqlalchemy import text

from tests.conftest import corps_import, diagramme_autre, diagramme_exemple, en_tete, i

pytestmark = pytest.mark.integration


def _importer(client, monde, utilisateur="responsable", **kwargs):
    return client.post(f"/api/projets/{monde['projet']}/import", json=corps_import(**kwargs), headers=en_tete(monde[utilisateur]))


def _compter(db, table, **filtre):
    clause = " AND ".join(f"{k} = :{k}" for k in filtre) or "true"
    return db.execute(text(f"SELECT count(*) FROM {table} WHERE {clause}"), filtre).scalar_one()


def test_import_complet(client_db, db_session, monde):
    reponse = _importer(client_db, monde)

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["numero_sequence"] == 1 and corps["nb_elements_crees"] == 8
    assert set(corps) == {"id_import", "numero_sequence", "nb_elements_crees", "avertissements"}  # § 5.1.4 : pas d'id_version
    assert corps["avertissements"] == []

    p = {"id_projet": monde["projet"]}
    assert _compter(db_session, "element_schema", nature="TABLE", **p) == 2
    assert _compter(db_session, "element_schema", nature="COLONNE", **p) == 4
    relations = db_session.execute(
        text("""SELECT count(*) FROM relation r JOIN element_schema e ON e.id_element = r.id_colonne_source
                WHERE e.id_projet = :p"""), {"p": monde["projet"]}).scalar_one()
    assert relations == 1
    assert _compter(db_session, "operation", **p) == 1
    assert _compter(db_session, "evenement_journal", nature="IMPORT", **p) == 1
    assert _compter(db_session, "version", **p) == 0
    details = db_session.execute(text("SELECT details FROM evenement_journal WHERE nature = 'IMPORT' AND id_projet = :p"), {"p": monde["projet"]}).scalar_one()
    assert set(details) == {"id_import", "nb_elements_crees", "remplacement"}
    projet = db_session.execute(text("SELECT * FROM projet WHERE id_projet = :p"), {"p": monde["projet"]}).mappings().one()
    assert projet["type_base"] == "postgresql" and projet["numero_sequence"] == 1
    assert projet["annexes"]["areas"][0]["name"] == "Zone clients"
    dump = db_session.execute(text("SELECT * FROM import_dump WHERE id_projet = :p"), {"p": monde["projet"]}).mappings().one()
    assert dump["nb_elements_crees"] == 8
    assert dump["id_version_produite"] is None  # l'import ne crée pas de version (CU 1.5, RG-17)
    assert dump["rapport"]["elements_crees"]["tables"] == 2
    assert dump["rapport"]["non_repris"][0]["type"] == "INSERT"


def test_schema_non_vide_demande_confirmation(client_db, db_session, monde):
    assert _importer(client_db, monde).status_code == 201

    reponse = _importer(client_db, monde, diagramme=diagramme_exemple())

    assert reponse.status_code == 409
    assert reponse.json()["detail"] == {"code": "CONFIRMATION_REQUISE", "nb_tables_existantes": 2}
    assert _compter(db_session, "import_dump", id_projet=monde["projet"]) == 1


def test_remplacement_apres_confirmation(client_db, db_session, monde):
    _importer(client_db, monde)

    reponse = _importer(client_db, monde, diagramme=diagramme_autre(), confirme_remplacement=True)

    assert reponse.status_code == 201 and reponse.json()["numero_sequence"] == 2
    actives = db_session.execute(
        text("SELECT id_element FROM element_schema WHERE id_projet = :p AND nature = 'TABLE' AND date_suppression IS NULL"),
        {"p": monde["projet"]},
    ).scalars().all()
    assert actives == [i("t_autre")]
    # rien n'est effacé : l'ancien état reste, supprimé logiquement
    assert _compter(db_session, "element_schema", id_projet=monde["projet"]) == 6 + 2
    # l'import ne crée jamais de version : c'est l'utilisateur qui en crée une, nommée (CU 3.1)
    assert _compter(db_session, "version", id_projet=monde["projet"]) == 0
    imports = db_session.execute(text("SELECT id_version_produite FROM import_dump WHERE id_projet = :p"), {"p": monde["projet"]}).scalars().all()
    assert imports == [None, None]  # deux imports sans version : la contrainte d'unicité accepte les valeurs vides


def test_refus_si_non_responsable(client_db, monde):
    assert _importer(client_db, monde, utilisateur="relecteur").status_code == 403


def test_refus_si_non_participant(client_db, monde):
    assert _importer(client_db, monde, utilisateur="etranger").status_code == 403


def test_utilisateur_non_identifie(client_db, monde):
    reponse = client_db.post(f"/api/projets/{monde['projet']}/import", json=corps_import())
    assert reponse.status_code == 401


def test_projet_inconnu(client_db, monde):
    from uuid import uuid4

    reponse = client_db.post(f"/api/projets/{uuid4()}/import", json=corps_import(), headers=en_tete(monde["responsable"]))
    assert reponse.status_code == 404


def test_fichier_trop_gros(client_db, monde):
    corps = corps_import()
    corps["fichier"]["taille_octets"] = 10**12

    reponse = client_db.post(f"/api/projets/{monde['projet']}/import", json=corps, headers=en_tete(monde["responsable"]))

    assert reponse.status_code == 413


def test_diagramme_invalide_ne_cree_rien(client_db, db_session, monde):
    d = diagramme_exemple()
    d["relationships"][0]["sourceFieldId"] = "inconnue"

    reponse = _importer(client_db, monde, diagramme=d)

    assert reponse.status_code == 422
    assert _compter(db_session, "element_schema", id_projet=monde["projet"]) == 0


def test_identifiant_deja_utilise(client_db, db_session, monde):
    _importer(client_db, monde)

    reponse = _importer(client_db, monde, confirme_remplacement=True)  # mêmes identifiants ChartDB

    assert reponse.status_code == 422
    assert _compter(db_session, "import_dump", id_projet=monde["projet"]) == 1  # le premier import est intact


def test_le_rapport_ne_peut_pas_contenir_le_texte_d_une_instruction(client_db, monde):
    rapport = {"non_repris": [{"ligne": 1, "type": "INSERT", "raison": "données", "instruction": "INSERT INTO ..."}]}

    reponse = _importer(client_db, monde, rapport=rapport)

    assert reponse.status_code == 422

def test_avertissements_sur_les_noms_et_les_types(client_db, db_session, monde):
    """Un mot réservé ou un type inconnu du dialecte n'empêche pas l'import (EX-14) : il est signalé (EX-05)."""
    d = diagramme_exemple()
    d["tables"][0]["name"] = "user"
    d["tables"][0]["fields"][1]["type"] = {"id": "citext"}

    reponse = _importer(client_db, monde, diagramme=d)

    assert reponse.status_code == 201, reponse.text
    codes = [(a["code"], a["id_element"]) for a in reponse.json()["avertissements"]]
    assert codes == [("NOM_RESERVE", i("t_client")), ("TYPE_INCONNU", i("c_client_nom"))]
    rapport = db_session.execute(text("SELECT rapport FROM import_dump WHERE id_projet = :p"), {"p": monde["projet"]}).scalar_one()
    assert [a["code"] for a in rapport["avertissements"]] == ["NOM_RESERVE", "TYPE_INCONNU"]


def test_deux_tables_de_meme_nom_a_la_casse_pres_refusees(client_db, db_session, monde):
    d = diagramme_exemple()
    d["tables"][1]["name"] = "Client"

    assert _importer(client_db, monde, diagramme=d).status_code == 422
    assert _compter(db_session, "import_dump", id_projet=monde["projet"]) == 0
