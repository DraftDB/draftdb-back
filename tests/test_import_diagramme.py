"""Tests sans base : validation du diagramme et traduction en lignes de tables."""

import copy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.chartdb import Diagramme
from app.services.importer import annexes_depuis, construire_lignes
from tests.conftest import diagramme_exemple, i


def test_traduction_en_lignes():
    diagramme = Diagramme.model_validate(diagramme_exemple())

    lignes = construire_lignes(diagramme, uuid4())

    assert [e["nature"] for e in lignes.elements].count("TABLE") == 2
    assert [e["nature"] for e in lignes.elements].count("COLONNE") == 4
    assert len(lignes.index) == 1 and len(lignes.relations) == 1
    assert lignes.nb_elements == 2 + 4 + 1 + 1
    assert [c["rang"] for c in lignes.colonnes if c["id_table"] == i("t_client")] == [1, 2]
    assert lignes.colonnes_index == [{"id_index": i("i_client_pk"), "id_colonne": i("c_client_id"), "rang": 1}]


def test_annexes_au_format_chartdb():
    annexes = annexes_depuis(Diagramme.model_validate(diagramme_exemple()))

    assert annexes["areas"][0]["name"] == "Zone clients"
    assert set(annexes) == {"areas", "notes", "customTypes", "dependencies"}


def _modifie(fonction):
    d = copy.deepcopy(diagramme_exemple())
    fonction(d)
    return d


@pytest.mark.parametrize("modification, message", [
    (lambda d: d["tables"][0]["fields"][0].update(nullable=True), "RG-12"),
    (lambda d: d["tables"][0].update(id="x" * 26), "at most 25"),
    (lambda d: d["relationships"][0].update(sourceFieldId="inconnue"), "absente du diagramme"),
    (lambda d: d["relationships"][0].update(sourceFieldId=i("c_client_id")), "elle-même"),
    (lambda d: d["tables"][1].update(id=i("t_client")), "en double"),
    (lambda d: d["tables"][0]["indexes"][0].update(fieldIds=[i("c_cmd_id")]), "absentes de sa table"),
    (lambda d: d["relationships"][0].update(sourceCardinality="beaucoup"), "one"),
])
def test_diagramme_invalide(modification, message):
    with pytest.raises(ValidationError, match=message):
        Diagramme.model_validate(_modifie(modification))