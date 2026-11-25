"""Tests de l'ajout d'une table (CU 2.1) contre la vraie base PostgreSQL."""
import copy
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.conftest import en_tete, i

pytestmark = pytest.mark.integration


def table_exemple(**remplacements) -> dict:
    t = {
        "id": i("t_client"), "name": "client", "x": 10, "y": 20, "color": "#8eb7ff", "isView": False,
        "fields": [
            {"id": i("c_id"), "name": "id", "type": {"id": "integer", "name": "integer"},
             "primaryKey": True, "unique": True, "nullable": False, "increment": True},
            {"id": i("c_nom"), "name": "nom", "type": {"id": "varchar", "name": "varchar"},
             "primaryKey": False, "unique": False, "nullable": False, "characterMaximumLength": "100"},
        ],
        "indexes": [{"id": i("i_pk"), "name": "client_pkey", "unique": True, "fieldIds": [i("c_id")], "isPrimaryKey": True}],
    }
    t.update(remplacements)
    return t


def _ajouter(client, monde, corps, utilisateur="responsable", projet=None):
    return client.post(f"/api/projets/{projet or monde['projet']}/tables", json=corps, headers=en_tete(monde[utilisateur]))


def _un(db, sql, **p):
    return db.execute(text(sql), p).scalar_one()


def test_ajout_nominal(client_db, monde, db_session):
    r = _ajouter(client_db, monde, table_exemple())
    assert r.status_code == 201
    c = r.json()
    assert c["numero_sequence"] == 1 and c["avertissement"] is None
    assert c["avertissements"] == [] and c["restauree"] is False
    assert c["table"]["id"] == i("t_client") and [f["id"] for f in c["table"]["fields"]] == [i("c_id"), i("c_nom")]
    assert c["table"]["x"] == 10 and "schema" not in c["table"]  # pas de null dans la réponse

    p = monde["projet"]
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p AND date_suppression IS NULL", p=p) == 3
    t = db_session.execute(text("SELECT * FROM table_schema WHERE id_element = :i"), {"i": i("t_client")}).mappings().one()
    assert t["nom"] == "client" and float(t["position_x"]) == 10 and t["couleur"] == "#8eb7ff"
    cols = db_session.execute(text("SELECT id_element, rang, cle_primaire, taille FROM colonne WHERE id_table = :i ORDER BY rang"), {"i": i("t_client")}).all()
    assert [(c_[0], c_[1]) for c_ in cols] == [(i("c_id"), 1), (i("c_nom"), 2)] and cols[0][2] is True and cols[1][3] == "100"
    assert db_session.execute(text("SELECT id_colonne, rang FROM colonne_index WHERE id_index = :i"), {"i": i("i_pk")}).all() == [(i("c_id"), 1)]
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=p) == 1
    op = db_session.execute(text("SELECT * FROM operation WHERE id_projet = :p"), {"p": p}).mappings().one()
    assert (op["numero_sequence"], op["cible"], op["action"], op["id_entite"]) == (1, "table", "ajout", i("t_client"))
    assert op["donnees_avant"] is None and op["donnees_apres"]["id"] == i("t_client") and op["id_auteur"] == monde["responsable"]
    assert _un(db_session, "SELECT count(*) FROM evenement_journal WHERE id_projet = :p", p=p) == 0  # pas d'événement du journal d'activité


def test_sans_cle_primaire_avertissement_non_bloquant(client_db, monde):
    t = table_exemple()
    t["fields"][0].update(primaryKey=False)
    r = _ajouter(client_db, monde, t)
    assert r.status_code == 201 and r.json()["avertissement"]["code"] == "TABLE_SANS_CLE_PRIMAIRE"


def test_table_vide_acceptee_avec_avertissement(client_db, monde):
    r = _ajouter(client_db, monde, {"id": i("t_vide"), "name": "vide"})
    assert r.status_code == 201 and r.json()["avertissement"]["code"] == "TABLE_SANS_CLE_PRIMAIRE"
    assert r.json()["table"]["fields"] == [] and r.json()["table"]["indexes"] == []


def test_numero_de_sequence_croissant(client_db, monde):
    a = _ajouter(client_db, monde, table_exemple())
    b = _ajouter(client_db, monde, {"id": i("t_autre"), "name": "autre"})
    assert (a.json()["numero_sequence"], b.json()["numero_sequence"]) == (1, 2)


def test_la_table_apparait_a_l_ouverture_du_projet(client_db, monde):
    _ajouter(client_db, monde, table_exemple())
    d = client_db.get(f"/api/projets/{monde['projet']}", headers=en_tete(monde["responsable"])).json()
    assert d["numero_sequence"] == 1
    t = d["diagramme"]["tables"][0]
    assert t["id"] == i("t_client") and [f["id"] for f in t["fields"]] == [i("c_id"), i("c_nom")] and t["indexes"][0]["fieldIds"] == [i("c_id")]


def test_meme_nom_dans_un_autre_schema_sql_accepte(client_db, monde):
    assert _ajouter(client_db, monde, table_exemple(schema="a")).status_code == 201
    autre = {"id": i("t_b"), "name": "client", "schema": "b"}
    assert _ajouter(client_db, monde, autre).status_code == 201


@pytest.mark.parametrize("en_tetes", [{}, {"X-User-Id": "pas-un-uuid"}, {"X-User-Id": str(uuid4())}])
def test_401(client_db, monde, en_tetes):
    assert client_db.post(f"/api/projets/{monde['projet']}/tables", json=table_exemple(), headers=en_tetes).status_code == 401


@pytest.mark.parametrize("utilisateur", ["relecteur", "etranger"])
def test_403_si_pas_concepteur_et_rien_ecrit(client_db, monde, db_session, utilisateur):
    assert _ajouter(client_db, monde, table_exemple(), utilisateur=utilisateur).status_code == 403
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p", p=monde["projet"]) == 0
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 0


def test_responsable_sans_role_concepteur_refuse(client_db, monde, db_session):
    db_session.execute(text("UPDATE participation SET est_concepteur = false, est_relecteur = true WHERE id_utilisateur = :u"), {"u": monde["responsable"]})
    assert _ajouter(client_db, monde, table_exemple()).status_code == 403


def test_ordre_401_403_422(client_db, monde):
    invalide = {"id": "x", "name": "n", "fields": [{"id": "f", "name": "f"}]}  # type de colonne absent
    assert client_db.post(f"/api/projets/{monde['projet']}/tables", json=invalide).status_code == 401
    assert _ajouter(client_db, monde, invalide, utilisateur="etranger").status_code == 403   # 403 avant 422
    assert _ajouter(client_db, monde, invalide).status_code == 422


def test_404_projet_inconnu(client_db, monde):
    assert _ajouter(client_db, monde, table_exemple(), projet=uuid4()).status_code == 404


def _mod(f):
    t = copy.deepcopy(table_exemple()); f(t); return t


@pytest.mark.parametrize("corps", [
    {},                                                                    # id et name absents
    {"id": "t1"},                                                          # nom absent
    {"id": "t1", "name": ""}, {"id": "t1", "name": "   "}, {"id": "t1", "name": "n" * 64},
    {"id": "x" * 26, "name": "n"},                                         # id trop long
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "f"}]},       # type de colonne absent
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "f", "type": {"id": "int"}, "primaryKey": True, "nullable": True}]},  # RG-12
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": " ", "type": {"id": "int"}}]},
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "a", "type": {"id": "int"}}, {"id": "g", "name": "a", "type": {"id": "int"}}]},  # RG-10 colonnes
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "a", "type": {"id": "int"}}, {"id": "f", "name": "b", "type": {"id": "int"}}]},  # id en double
    {"id": "t1", "name": "n", "fields": [{"id": "t1", "name": "a", "type": {"id": "int"}}]},                                                 # id colonne = id table
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "a", "type": {"id": "int"}}], "indexes": [{"id": "i", "name": "i", "fieldIds": ["inconnue"]}]},  # RG-14
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "a", "type": {"id": "int"}}], "indexes": [{"id": "i", "name": "i", "fieldIds": ["f", "f"]}]},
    {"id": "t1", "name": "n", "x": 10**9},
])
def test_422_table_invalide_et_rien_ecrit(client_db, monde, db_session, corps):
    r = _ajouter(client_db, monde, corps)
    assert r.status_code == 422
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p", p=monde["projet"]) == 0
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 0


def test_422_nom_deja_pris_RG10(client_db, monde, db_session):
    assert _ajouter(client_db, monde, table_exemple()).status_code == 201
    r = _ajouter(client_db, monde, _mod(lambda t: t.update(id=i("t_2"), fields=[], indexes=[])))
    assert r.status_code == 422 and "RG-10" in r.json()["detail"]
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 1


def test_nom_d_une_table_supprimee_logiquement_est_reutilisable(client_db, monde, db_session):
    _ajouter(client_db, monde, table_exemple())
    db_session.execute(text("UPDATE element_schema SET date_suppression = now() WHERE id_projet = :p"), {"p": monde["projet"]})
    assert _ajouter(client_db, monde, {"id": i("t_neuve"), "name": "client"}).status_code == 201


def test_nom_identique_dans_un_autre_projet_accepte(client_db, monde, db_session):
    autre = uuid4()
    db_session.execute(text("INSERT INTO projet (id_projet, nom, id_responsable) VALUES (:p, 'Autre', :r)"), {"p": autre, "r": monde["responsable"]})
    db_session.execute(text("INSERT INTO participation (id_utilisateur, id_projet, est_concepteur) VALUES (:r, :p, true)"), {"p": autre, "r": monde["responsable"]})
    assert _ajouter(client_db, monde, table_exemple()).status_code == 201
    assert _ajouter(client_db, monde, {"id": i("t_ailleurs"), "name": "client"}, projet=autre).status_code == 201


@pytest.mark.parametrize("id_table, id_colonne, id_index", [
    ("t_client", "c_neuf", "i_neuf"),   # id de table déjà pris
    ("t_neuf", "c_id", "i_neuf"),       # id de colonne déjà pris
    ("t_neuf", "c_neuf", "i_pk"),       # id d'index déjà pris
])
def test_422_identifiant_deja_utilise_P3(client_db, monde, db_session, id_table, id_colonne, id_index):
    assert _ajouter(client_db, monde, table_exemple()).status_code == 201
    autre = {
        "id": i(id_table), "name": "autre",
        "fields": [{"id": i(id_colonne), "name": "a", "type": {"id": "int"}, "primaryKey": True, "nullable": False}],
        "indexes": [{"id": i(id_index), "name": "idx", "fieldIds": [i(id_colonne)]}],
    }
    r = _ajouter(client_db, monde, autre)
    assert r.status_code == 422 and "P3" in r.json()["detail"]
    assert _un(db_session, "SELECT numero_sequence FROM projet WHERE id_projet = :p", p=monde["projet"]) == 1


# --- Restauration d'une table supprimée (RG-09 précisée, AUD-06) -------------------------------------------

def _supprimer(client, monde, id_table, projet=None):
    r = client.delete(f"/api/projets/{projet or monde['projet']}/tables/{id_table}",
                      params={"confirme_suppression": True}, headers=en_tete(monde["responsable"]))
    assert r.status_code == 200, r.text
    return r


def _ouvrir(client, monde):
    return client.get(f"/api/projets/{monde['projet']}", headers=en_tete(monde["responsable"])).json()["diagramme"]


def test_restauration_d_une_table_supprimee_meme_identifiant(client_db, monde, db_session):
    """Annuler une suppression : la même table (mêmes identifiants) est de nouveau acceptée."""
    _ajouter(client_db, monde, table_exemple())
    _supprimer(client_db, monde, i("t_client"))

    r = _ajouter(client_db, monde, table_exemple())

    assert r.status_code == 201, r.text
    assert r.json()["restauree"] is True and r.json()["numero_sequence"] == 3
    t = _ouvrir(client_db, monde)["tables"][0]
    assert t["id"] == i("t_client") and [f["id"] for f in t["fields"]] == [i("c_id"), i("c_nom")]
    assert [x["id"] for x in t["indexes"]] == [i("i_pk")] and t["indexes"][0]["fieldIds"] == [i("c_id")]
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p AND date_suppression IS NULL",
               p=monde["projet"]) == 3
    actions = db_session.execute(text("SELECT action FROM operation WHERE id_projet = :p ORDER BY numero_sequence"),
                                 {"p": monde["projet"]}).scalars().all()
    assert actions == ["ajout", "suppression", "ajout"]  # l'historique garde les trois étapes (P4)


def test_restauration_le_corps_recu_devient_l_etat_de_la_table(client_db, monde, db_session):
    """Nom, colonnes et index du corps remplacent l'ancien état ; une ancienne colonne absente reste supprimée."""
    _ajouter(client_db, monde, table_exemple())
    _supprimer(client_db, monde, i("t_client"))
    corps = table_exemple(name="clients", indexes=[])
    corps["fields"] = [corps["fields"][0], {"id": i("c_neuve"), "name": "email", "type": {"id": "varchar"}}]

    r = _ajouter(client_db, monde, corps)

    assert r.status_code == 201 and r.json()["restauree"] is True
    t = _ouvrir(client_db, monde)["tables"][0]
    assert t["name"] == "clients" and [f["id"] for f in t["fields"]] == [i("c_id"), i("c_neuve")] and t["indexes"] == []
    assert _un(db_session, "SELECT count(*) FROM index_schema WHERE id_index = :i", i=i("i_pk")) == 0
    assert _un(db_session, "SELECT date_suppression IS NOT NULL FROM element_schema WHERE id_element = :i", i=i("c_nom"))


def test_restauration_retrouve_les_relations_de_la_table(client_db, monde, db_session):
    _ajouter(client_db, monde, table_exemple())
    commande = {"id": i("t_cmd"), "name": "commande", "fields": [
        {"id": i("c_cmd_id"), "name": "id", "type": {"id": "int"}, "primaryKey": True, "nullable": False},
        {"id": i("c_cmd_client"), "name": "client_id", "type": {"id": "int"}}]}
    _ajouter(client_db, monde, commande)
    db_session.execute(text("""INSERT INTO relation (id_relation, nom, cardinalite_source, cardinalite_cible,
                                                     id_colonne_source, id_colonne_cible)
                               VALUES (:r, 'fk', 'many', 'one', :s, :c)"""),
                       {"r": i("r_fk"), "s": i("c_cmd_client"), "c": i("c_id")})
    _supprimer(client_db, monde, i("t_client"))
    assert _ouvrir(client_db, monde)["relationships"] == []

    assert _ajouter(client_db, monde, table_exemple()).status_code == 201

    assert [r["id"] for r in _ouvrir(client_db, monde)["relationships"]] == [i("r_fk")]


def test_identifiant_d_une_table_supprimee_d_un_autre_projet_refuse(client_db, monde, db_session):
    autre = uuid4()
    db_session.execute(text("INSERT INTO projet (id_projet, nom, id_responsable) VALUES (:p, 'Autre', :r)"), {"p": autre, "r": monde["responsable"]})
    db_session.execute(text("INSERT INTO participation (id_utilisateur, id_projet, est_concepteur) VALUES (:r, :p, true)"), {"p": autre, "r": monde["responsable"]})
    assert _ajouter(client_db, monde, table_exemple(), projet=autre).status_code == 201
    _supprimer(client_db, monde, i("t_client"), projet=autre)

    r = _ajouter(client_db, monde, table_exemple())

    assert r.status_code == 422 and "P3" in r.json()["detail"]


def test_restauration_refuse_la_colonne_d_une_autre_table(client_db, monde):
    _ajouter(client_db, monde, table_exemple())
    _ajouter(client_db, monde, {"id": i("t_autre"), "name": "autre",
                                "fields": [{"id": i("c_autre"), "name": "a", "type": {"id": "int"}}]})
    _supprimer(client_db, monde, i("t_client"))
    corps = table_exemple()
    corps["fields"].append({"id": i("c_autre"), "name": "volee", "type": {"id": "int"}})

    r = _ajouter(client_db, monde, corps)

    assert r.status_code == 422 and i("c_autre") in r.json()["detail"]


def test_restauration_refusee_si_le_nom_a_ete_repris(client_db, monde):
    _ajouter(client_db, monde, table_exemple())
    _supprimer(client_db, monde, i("t_client"))
    _ajouter(client_db, monde, {"id": i("t_nouvelle"), "name": "client"})

    r = _ajouter(client_db, monde, table_exemple())

    assert r.status_code == 422 and "RG-10" in r.json()["detail"]


# --- Noms (RG-10 précisée, AUD-02) -------------------------------------------------------------------------

def test_422_nom_deja_pris_sans_tenir_compte_de_la_casse(client_db, monde):
    assert _ajouter(client_db, monde, table_exemple(name="Client")).status_code == 201
    r = _ajouter(client_db, monde, {"id": i("t_2"), "name": "CLIENT"})
    assert r.status_code == 422 and "casse" in r.json()["detail"]


@pytest.mark.parametrize("nom", ['a"; DROP TABLE x;--', "a`b", "tab\tulation", " client", "client ", "é" * 32])
def test_422_nom_inutilisable_en_sql(client_db, monde, db_session, nom):
    r = _ajouter(client_db, monde, {"id": i("t_nom"), "name": nom})
    assert r.status_code == 422
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_projet = :p", p=monde["projet"]) == 0


def test_mot_reserve_et_nom_a_proteger_acceptes_avec_avertissement(client_db, monde):
    corps = {"id": i("t_sel"), "name": "select", "fields": [
        {"id": i("c_k"), "name": "id", "type": {"id": "int"}, "primaryKey": True, "nullable": False},
        {"id": i("c_n"), "name": "Nom client", "type": {"id": "varchar"}}]}

    r = _ajouter(client_db, monde, corps)

    assert r.status_code == 201 and r.json()["avertissement"] is None  # la table a une clé primaire
    codes = [(a["code"], a["id_element"]) for a in r.json()["avertissements"]]
    assert codes == [("NOM_RESERVE", i("t_sel")), ("NOM_A_PROTEGER", i("c_n"))]


# --- Types (RG-11 précisée, AUD-03) ------------------------------------------------------------------------

def _table_type(type_id):
    return {"id": i("t_typ"), "name": "typee", "fields": [{"id": i("c_typ"), "name": "f", "type": {"id": type_id}}]}


@pytest.mark.parametrize("type_base, type_id, attendu", [
    ("generic", "nimportequoi", 422),
    ("generic", "tinyint", 422),        # propre à MySQL : pas dans un projet générique
    ("generic", "INTEGER", 201),        # synonyme commun, casse ignorée
    ("mysql", "tinyint", 201),
    ("mysql", "jsonb", 422),            # propre à PostgreSQL
    ("postgresql", "jsonb", 201),
    ("postgresql", "character varying", 201),
])
def test_type_de_colonne_selon_le_dialecte_du_projet(client_db, monde, db_session, type_base, type_id, attendu):
    db_session.execute(text("UPDATE projet SET type_base = :t WHERE id_projet = :p"), {"t": type_base, "p": monde["projet"]})

    r = _ajouter(client_db, monde, _table_type(type_id))

    assert r.status_code == attendu, r.text
    if attendu == 422:
        assert "RG-11" in r.json()["detail"]


def test_type_personnalise_du_projet_admis(client_db, monde, db_session):
    db_session.execute(text("""UPDATE projet SET annexes = '{"customTypes": [{"id": "ct1", "name": "humeur", "kind": "enum"}]}'
                               WHERE id_projet = :p"""), {"p": monde["projet"]})
    assert _ajouter(client_db, monde, _table_type("humeur")).status_code == 201


@pytest.mark.parametrize("corps", [
    {"id": "t1", "name": "a\x00b"},
    {"id": "t1", "name": "n", "fields": [{"id": "f", "name": "a", "type": {"id": "int"}, "comments": "x\x00y"}]},
])
def test_nul_422_et_rollback(client_db, monde, db_session, corps):
    corps = copy.deepcopy(corps); corps["id"] = i("t_nul")
    for k, f in enumerate(corps.get("fields", [])): f["id"] = i(f"c_nul{k}")
    assert _ajouter(client_db, monde, corps).status_code == 422
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_element = :i", i=i("t_nul")) == 0


def test_atomicite_si_l_operation_echoue(client_db, monde, db_session, monkeypatch):
    """La table, ses colonnes et ses index sont écrits AVANT l'opération : si elle échoue, tout est annulé."""
    from app.services import tables as svc
    def casse(*a, **k):
        raise svc.DataError("INSERT", {}, Exception("boom"))
    monkeypatch.setattr(svc, "bindparam", casse)
    assert _ajouter(client_db, monde, table_exemple()).status_code == 422
    assert _un(db_session, "SELECT count(*) FROM element_schema WHERE id_element = :i", i=i("t_client")) == 0
    assert _un(db_session, "SELECT count(*) FROM index_schema WHERE id_index = :i", i=i("i_pk")) == 0


def test_swagger_expose_la_route(client_db):
    assert "post" in client_db.get("/api/openapi.json").json()["paths"]["/api/projets/{id_projet}/tables"]