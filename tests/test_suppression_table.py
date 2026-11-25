"""Tests de la suppression d'une table (CU 2.3) contre la vraie base PostgreSQL."""
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.conftest import en_tete, i

pytestmark = pytest.mark.integration


def table_client() -> dict:
    return {
        "id": i("t_client"), "name": "client",
        "fields": [
            {"id": i("c_id"), "name": "id", "type": {"id": "integer"}, "primaryKey": True, "nullable": False},
            {"id": i("c_nom"), "name": "nom", "type": {"id": "varchar"}, "nullable": False},
        ],
        "indexes": [{"id": i("i_pk"), "name": "client_pkey", "unique": True, "fieldIds": [i("c_id")], "isPrimaryKey": True}],
    }


def table_commande() -> dict:
    return {
        "id": i("t_cmd"), "name": "commande",
        "fields": [
            {"id": i("c_cmd_id"), "name": "id", "type": {"id": "integer"}, "primaryKey": True, "nullable": False},
            {"id": i("c_cmd_client"), "name": "client_id", "type": {"id": "integer"}, "nullable": False},
        ],
    }


def _ajouter(client, monde, table, projet=None, utilisateur="responsable"):
    r = client.post(f"/api/projets/{projet or monde['projet']}/tables", json=table, headers=en_tete(monde[utilisateur]))
    assert r.status_code == 201, r.text
    return r


def _supprimer(client, monde, id_table, confirme=None, utilisateur="responsable", projet=None):
    params = {} if confirme is None else {"confirme_suppression": confirme}
    return client.delete(f"/api/projets/{projet or monde['projet']}/tables/{id_table}", params=params,
                         headers=en_tete(monde[utilisateur]))


def _relier(db, id_rel, col_source, col_cible):
    db.execute(text("""INSERT INTO relation (id_relation, nom, cardinalite_source, cardinalite_cible, id_colonne_source, id_colonne_cible)
                       VALUES (:i, 'fk_commande_client', 'many', 'one', :s, :c)"""), {"i": id_rel, "s": col_source, "c": col_cible})


def _un(db, sql, **p):
    return db.execute(text(sql), p).scalar_one()


def _supprimes(db, projet):
    return _un(db, "SELECT count(*) FROM element_schema WHERE id_projet = :p AND date_suppression IS NOT NULL", p=projet)


def test_sans_confirmation_409_et_rien_n_est_ecrit(client_db, monde, db_session):
    _ajouter(client_db, monde, table_client())
    r = _supprimer(client_db, monde, i("t_client"))
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "CONFIRMATION_REQUISE" and d["cles_etrangeres"] == []
    assert d["index"] == [{"id": i("i_pk"), "name": "client_pkey"}]
    assert _supprimes(db_session, monde["projet"]) == 0
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 1
    assert _un(db_session, "SELECT count(*) FROM operation WHERE action = 'suppression' AND id_projet = :p", p=monde["projet"]) == 0


def test_409_meme_sans_aucun_lien(client_db, monde):
    _ajouter(client_db, monde, {"id": i("t_seule"), "name": "seule"})
    r = _supprimer(client_db, monde, i("t_seule"))
    assert r.status_code == 409 and r.json()["detail"] == {"code": "CONFIRMATION_REQUISE", "cles_etrangeres": [], "index": []}


def test_confirme_suppression_false_explicite_donne_409(client_db, monde):
    _ajouter(client_db, monde, table_client())
    assert _supprimer(client_db, monde, i("t_client"), confirme=False).status_code == 409


@pytest.mark.parametrize("qui", ["t_client", "t_cmd"])  # la table est la cible, puis la source de la clé étrangère
def test_409_liste_les_cles_etrangeres_dans_les_deux_sens(client_db, monde, db_session, qui):
    _ajouter(client_db, monde, table_client())
    _ajouter(client_db, monde, table_commande())
    _relier(db_session, i("r_fk"), i("c_cmd_client"), i("c_id"))
    d = _supprimer(client_db, monde, i(qui)).json()["detail"]
    assert d["cles_etrangeres"] == [{
        "id": i("r_fk"), "name": "fk_commande_client", "sourceTableId": i("t_cmd"), "targetTableId": i("t_client"),
        "sourceFieldId": i("c_cmd_client"), "targetFieldId": i("c_id"),
    }]


def test_suppression_confirmee_nominale(client_db, monde, db_session):
    _ajouter(client_db, monde, table_client())
    r = _supprimer(client_db, monde, i("t_client"), confirme=True)
    assert r.status_code == 200 and r.json() == {"id_table": i("t_client"), "numero_sequence": 2}

    p = monde["projet"]
    # P4 : rien n'est effacé, la table et ses colonnes portent une date de suppression
    assert _un(db_session, "SELECT count(*) FROM table_schema WHERE id_element = :i", i=i("t_client")) == 1
    assert _un(db_session, "SELECT count(*) FROM colonne WHERE id_table = :i", i=i("t_client")) == 2
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p AND date_suppression IS NOT NULL", p=p) == 3
    assert _un(db_session, "SELECT count(*) FROM index_schema WHERE id_table = :i", i=i("t_client")) == 1
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=p) == 2
    op = db_session.execute(text("SELECT * FROM operation WHERE id_projet = :p AND action = 'suppression'"), {"p": p}).mappings().one()
    assert (op["numero_sequence"], op["cible"], op["id_entite"]) == (2, "table", i("t_client"))
    assert op["donnees_apres"] is None and op["id_auteur"] == monde["responsable"]
    avant = op["donnees_avant"]  # l'état avant, au format ChartDB, pour pouvoir restituer la table
    assert avant["id"] == i("t_client") and [f["id"] for f in avant["fields"]] == [i("c_id"), i("c_nom")]
    assert [x["id"] for x in avant["indexes"]] == [i("i_pk")] and avant["indexes"][0]["fieldIds"] == [i("c_id")]
    assert _un(db_session, "SELECT count(*) FROM evenement_journal WHERE id_projet = :p", p=p) == 0


def test_la_table_et_ses_liens_disparaissent_du_schema(client_db, monde, db_session):
    _ajouter(client_db, monde, table_client())
    _ajouter(client_db, monde, table_commande())
    _relier(db_session, i("r_fk"), i("c_cmd_client"), i("c_id"))
    avant = client_db.get(f"/api/projets/{monde['projet']}", headers=en_tete(monde["responsable"])).json()["diagramme"]
    assert len(avant["tables"]) == 2 and len(avant["relationships"]) == 1

    assert _supprimer(client_db, monde, i("t_client"), confirme=True).status_code == 200
    d = client_db.get(f"/api/projets/{monde['projet']}", headers=en_tete(monde["responsable"])).json()
    assert [t["id"] for t in d["diagramme"]["tables"]] == [i("t_cmd")] and d["diagramme"]["relationships"] == []
    assert d["numero_sequence"] == 3


def test_le_nom_redevient_libre_et_l_identifiant_peut_etre_restaure(client_db, monde):
    _ajouter(client_db, monde, table_client())
    _supprimer(client_db, monde, i("t_client"), confirme=True)
    nouvelle = {"id": i("t_neuve"), "name": "client"}                               # RG-10 : nom libre
    assert client_db.post(f"/api/projets/{monde['projet']}/tables", json=nouvelle, headers=en_tete(monde["responsable"])).status_code == 201
    reprise = {"id": i("t_client"), "name": "autre"}                                 # RG-09 précisée : restauration
    r = client_db.post(f"/api/projets/{monde['projet']}/tables", json=reprise, headers=en_tete(monde["responsable"]))
    assert r.status_code == 201 and r.json()["restauree"] is True


def test_supprimer_deux_fois_donne_404(client_db, monde):
    _ajouter(client_db, monde, table_client())
    assert _supprimer(client_db, monde, i("t_client"), confirme=True).status_code == 200
    assert _supprimer(client_db, monde, i("t_client"), confirme=True).status_code == 404
    assert _supprimer(client_db, monde, i("t_client")).status_code == 404


def test_404_table_inconnue_ou_colonne_ou_projet_inconnu(client_db, monde):
    _ajouter(client_db, monde, table_client())
    assert _supprimer(client_db, monde, "inconnue", confirme=True).status_code == 404
    assert _supprimer(client_db, monde, i("c_id"), confirme=True).status_code == 404   # une colonne n'est pas une table
    assert _supprimer(client_db, monde, i("t_client"), confirme=True, projet=uuid4()).status_code == 404


def test_404_table_d_un_autre_projet_et_elle_reste_intacte(client_db, monde, db_session):
    autre = uuid4()
    db_session.execute(text("INSERT INTO projet (id_projet, nom, id_responsable) VALUES (:p, 'Autre', :r)"), {"p": autre, "r": monde["responsable"]})
    db_session.execute(text("INSERT INTO participation (id_utilisateur, id_projet, est_concepteur) VALUES (:r, :p, true)"), {"p": autre, "r": monde["responsable"]})
    _ajouter(client_db, monde, table_client(), projet=autre)
    assert _supprimer(client_db, monde, i("t_client"), confirme=True).status_code == 404
    assert _supprimes(db_session, autre) == 0


def test_nul_dans_l_identifiant_donne_404(client_db, monde):
    assert _supprimer(client_db, monde, "a%00b", confirme=True).status_code == 404


@pytest.mark.parametrize("en_tetes", [{}, {"X-User-Id": "pas-un-uuid"}, {"X-User-Id": str(uuid4())}])
def test_401(client_db, monde, en_tetes):
    assert client_db.delete(f"/api/projets/{monde['projet']}/tables/x", params={"confirme_suppression": True}, headers=en_tetes).status_code == 401


@pytest.mark.parametrize("utilisateur", ["relecteur", "etranger"])
def test_403_si_pas_concepteur_et_rien_supprime(client_db, monde, db_session, utilisateur):
    _ajouter(client_db, monde, table_client())
    assert _supprimer(client_db, monde, i("t_client"), confirme=True, utilisateur=utilisateur).status_code == 403
    assert _supprimes(db_session, monde["projet"]) == 0
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 1


def test_ordre_401_403_404_409(client_db, monde):
    """Les droits passent avant la recherche de la table : un non-concepteur ne peut pas sonder les identifiants."""
    _ajouter(client_db, monde, table_client())
    assert client_db.delete(f"/api/projets/{monde['projet']}/tables/{i('t_client')}").status_code == 401
    assert _supprimer(client_db, monde, "inconnue", utilisateur="etranger").status_code == 403   # 403 avant 404
    assert _supprimer(client_db, monde, "inconnue").status_code == 404                           # 404 avant 409
    assert _supprimer(client_db, monde, i("t_client")).status_code == 409


@pytest.mark.parametrize("valeur", ["true", "1", "True"])
def test_valeurs_vraies_de_confirmation(client_db, monde, valeur):
    _ajouter(client_db, monde, table_client())
    r = client_db.delete(f"/api/projets/{monde['projet']}/tables/{i('t_client')}?confirme_suppression={valeur}", headers=en_tete(monde["responsable"]))
    assert r.status_code == 200


def test_422_parametres_invalides(client_db, monde):
    assert _supprimer(client_db, monde, "x" * 26, confirme=True).status_code == 422
    r = client_db.delete(f"/api/projets/{monde['projet']}/tables/x?confirme_suppression=peut-etre", headers=en_tete(monde["responsable"]))
    assert r.status_code == 422


def test_une_colonne_deja_supprimee_garde_sa_date(client_db, monde, db_session):
    _ajouter(client_db, monde, table_client())
    db_session.execute(text("UPDATE element_schema SET date_suppression = '2020-01-01 00:00+00' WHERE id_element = :i"), {"i": i("c_nom")})
    _supprimer(client_db, monde, i("t_client"), confirme=True)
    d = _un(db_session, "SELECT date_suppression FROM element_schema WHERE id_element = :i", i=i("c_nom"))
    assert d.year == 2020


def test_ajout_puis_suppression_numerotation_continue(client_db, monde, db_session):
    _ajouter(client_db, monde, table_client())
    _ajouter(client_db, monde, table_commande())
    _supprimer(client_db, monde, i("t_client"), confirme=True)
    ops = db_session.execute(text("SELECT numero_sequence, action FROM operation WHERE id_projet = :p ORDER BY numero_sequence"), {"p": monde["projet"]}).all()
    assert [tuple(o) for o in ops] == [(1, "ajout"), (2, "ajout"), (3, "suppression")]


def test_atomicite_si_l_operation_echoue(client_db, monde, db_session, monkeypatch):
    """Si l'écriture de l'opération échoue, la suppression des éléments est annulée aussi."""
    from sqlalchemy.exc import DataError
    from app.services import tables as svc
    _ajouter(client_db, monde, table_client())

    def casse(*a, **k):
        raise DataError("INSERT", {}, Exception("boom"))
    monkeypatch.setattr(svc, "bindparam", casse)
    with pytest.raises(DataError):
        _supprimer(client_db, monde, i("t_client"), confirme=True)
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_element = :i AND date_suppression IS NOT NULL", i=i("t_client")) == 0


def test_swagger_expose_la_route(client_db):
    assert "delete" in client_db.get("/api/openapi.json").json()["paths"]["/api/projets/{id_projet}/tables/{id_table}"]