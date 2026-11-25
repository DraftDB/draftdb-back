"""Tests sans base : validation d'une table à ajouter (CU 2.1) et traduction en lignes de tables."""

import copy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.chartdb import Diagramme
from app.schemas.tables import TableAjout
from app.services.importer import construire_lignes
from app.schemas.regles import avertissement_cle_primaire as _avertissement, avertissements_table
from app.schemas.types_colonnes import types_admis


def table_valide() -> dict:
    return {
        "id": "t_client", "name": "client", "x": 10, "y": 20,
        "fields": [
            {"id": "c_id", "name": "id", "type": {"id": "integer"}, "primaryKey": True, "nullable": False},
            {"id": "c_nom", "name": "nom", "type": {"id": "varchar"}, "nullable": False, "characterMaximumLength": "100"},
        ],
        "indexes": [{"id": "i_pk", "name": "client_pkey", "fieldIds": ["c_id"], "isPrimaryKey": True}],
    }


def _modifie(fonction) -> dict:
    t = copy.deepcopy(table_valide())
    fonction(t)
    return t


def test_table_valide():
    table = TableAjout.model_validate(table_valide())

    assert table.id == "t_client" and [c.id for c in table.fields] == ["c_id", "c_nom"]


def test_table_minimale_sans_colonne_ni_index():
    table = TableAjout.model_validate({"id": "t1", "name": "vide"})

    assert table.fields == [] and table.indexes == [] and table.x == 0


def test_les_champs_inconnus_de_chartdb_sont_conserves():
    corps = table_valide() | {"createdAt": 1700000000000}

    table = TableAjout.model_validate(corps)

    assert table.model_dump(by_alias=True)["createdAt"] == 1700000000000


@pytest.mark.parametrize("modification, message", [
    (lambda t: t.pop("id"), "id"),
    (lambda t: t.pop("name"), "name"),
    (lambda t: t.update(name=""), "at least 1"),
    (lambda t: t.update(name="   "), "nom ne peut pas être vide"),
    (lambda t: t.update(name="n" * 64), "at most 63"),
    (lambda t: t.update(id="x" * 26), "at most 25"),
    (lambda t: t.update(x=10**9), "less than or equal"),
    (lambda t: t["fields"][0].pop("type"), "type"),                                        # type de colonne absent
    (lambda t: t["fields"][1].update(name=" "), "nom ne peut pas être vide"),
    (lambda t: t["fields"][1].update(name="id"), "RG-10"),                                 # deux colonnes de même nom
    (lambda t: t["fields"][1].update(id="c_id"), "Identifiant en double"),
    (lambda t: t["fields"][1].update(id="t_client"), "Identifiant en double"),             # id de colonne = id de table
    (lambda t: t["fields"][0].update(nullable=True), "RG-12"),                             # clé primaire nullable
    (lambda t: t["indexes"][0].update(fieldIds=["inconnue"]), "absentes de sa table"),     # RG-14
    (lambda t: t["indexes"][0].update(fieldIds=["c_id", "c_id"]), "deux fois la même colonne"),
    (lambda t: t["indexes"].append({"id": "i_pk", "name": "autre", "fieldIds": ["c_nom"]}), "Identifiant d'index en double"),
])
def test_table_invalide(modification, message):
    with pytest.raises(ValidationError, match=message):
        TableAjout.model_validate(_modifie(modification))


def test_traduction_en_lignes_avec_rang_des_colonnes():
    table = TableAjout.model_validate(table_valide())

    lignes = construire_lignes(Diagramme.model_construct(tables=[table]), uuid4())

    assert [e["nature"] for e in lignes.elements] == ["TABLE", "COLONNE", "COLONNE"]
    assert [(c["id"], c["rang"]) for c in lignes.colonnes] == [("c_id", 1), ("c_nom", 2)]
    assert lignes.colonnes_index == [{"id_index": "i_pk", "id_colonne": "c_id", "rang": 1}]
    assert lignes.relations == []


def test_avertissement_si_aucune_cle_primaire():
    sans_pk = TableAjout.model_validate(_modifie(lambda t: t["fields"][0].update(primaryKey=False)))

    avertissement = _avertissement(sans_pk)

    assert avertissement.code == "TABLE_SANS_CLE_PRIMAIRE" and "client" in avertissement.message


def test_pas_d_avertissement_avec_une_cle_primaire():
    assert _avertissement(TableAjout.model_validate(table_valide())) is None


def test_avertissement_pour_une_table_sans_colonne():
    assert _avertissement(TableAjout.model_validate({"id": "t1", "name": "vide"})).code == "TABLE_SANS_CLE_PRIMAIRE"

# --- Règles de nommage (RG-10 précisée) et types (RG-11 précisée) ------------------------------------------

@pytest.mark.parametrize("nom, message", [
    ('a"b', "guillemet"),
    ("a`b", "guillemet"),
    ("a\tb", "caractère de contrôle"),
    (" client", "espace"),
    ("client ", "espace"),
    ("é" * 32, "63 octets"),                     # 32 caractères mais 64 octets en UTF-8
])
def test_nom_de_table_inutilisable_refuse(nom, message):
    with pytest.raises(ValidationError, match=message):
        TableAjout.model_validate(_modifie(lambda t: t.update(name=nom)))


def test_noms_de_colonnes_compares_sans_la_casse():
    with pytest.raises(ValidationError, match="casse"):
        TableAjout.model_validate(_modifie(lambda t: t["fields"][1].update(name="ID")))


def test_nom_accentue_de_63_octets_accepte():
    assert TableAjout.model_validate(_modifie(lambda t: t.update(name="é" * 31 + "a"))).name.startswith("é")


@pytest.mark.parametrize("nom, code", [
    ("select", "NOM_RESERVE"), ("USER", "NOM_RESERVE"), ("order", "NOM_RESERVE"),
    ("Nom client", "NOM_A_PROTEGER"), ("1ere", "NOM_A_PROTEGER"), ("café", "NOM_A_PROTEGER"),
])
def test_avertissement_sur_le_nom_de_la_table(nom, code):
    table = TableAjout.model_validate(_modifie(lambda t: t.update(name=nom)))
    assert [a.code for a in avertissements_table(table)] == [code]


def test_pas_d_avertissement_pour_un_nom_simple():
    assert avertissements_table(TableAjout.model_validate(table_valide())) == []


def test_types_admis_selon_le_dialecte():
    assert "tinyint" not in types_admis("generic") and "tinyint" in types_admis("mysql")
    assert "jsonb" in types_admis("postgresql") and "jsonb" not in types_admis("mysql")
    assert {"int", "integer", "varchar"} <= types_admis("generic")
    assert "humeur" in types_admis("generic", {"Humeur"})
