"""Reconstitution du diagramme ChartDB à partir de l'état courant (DRAFTDB-41, CU 1.6).

Le dossier (§ 3.2.6) : à l'ouverture, le serveur reconstitue les DBTable (avec leurs fields
et indexes) et les relations à partir des tables du schéma. Les éléments supprimés
logiquement (date_suppression) ne sont pas renvoyés.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def _ms(date: datetime) -> int:
    return int(date.timestamp() * 1000)


def _sans_none(valeurs: dict) -> dict:
    return {cle: valeur for cle, valeur in valeurs.items() if valeur is not None}


def reconstituer_diagramme(db: Session, projet) -> dict:
    p = {"p": projet["id_projet"]}
    tables = db.execute(text("""
        SELECT t.*, e.date_creation FROM table_schema t
        JOIN element_schema e ON e.id_element = t.id_element
        WHERE e.id_projet = :p AND e.date_suppression IS NULL
        ORDER BY e.date_creation, t.id_element"""), p).mappings().all()
    colonnes = db.execute(text("""
        SELECT c.*, e.date_creation FROM colonne c
        JOIN element_schema e ON e.id_element = c.id_element
        WHERE e.id_projet = :p AND e.date_suppression IS NULL
        ORDER BY c.id_table, c.rang"""), p).mappings().all()
    index = db.execute(text("""
        SELECT i.* FROM index_schema i
        JOIN element_schema e ON e.id_element = i.id_table
        WHERE e.id_projet = :p AND e.date_suppression IS NULL
        ORDER BY i.id_index"""), p).mappings().all()
    colonnes_index = db.execute(text("""
        SELECT ci.* FROM colonne_index ci
        JOIN index_schema i ON i.id_index = ci.id_index
        JOIN element_schema e ON e.id_element = i.id_table
        WHERE e.id_projet = :p AND e.date_suppression IS NULL
        ORDER BY ci.id_index, ci.rang"""), p).mappings().all()
    relations = db.execute(text("""
        SELECT r.*, cs.id_table AS id_table_source, cc.id_table AS id_table_cible, es.date_creation
        FROM relation r
        JOIN colonne cs ON cs.id_element = r.id_colonne_source
        JOIN colonne cc ON cc.id_element = r.id_colonne_cible
        JOIN element_schema es ON es.id_element = r.id_colonne_source
        JOIN element_schema ec ON ec.id_element = r.id_colonne_cible
        WHERE es.id_projet = :p AND es.date_suppression IS NULL AND ec.date_suppression IS NULL
        ORDER BY r.id_relation"""), p).mappings().all()

    visibles = {t["id_element"]: _ms(t["date_creation"]) for t in tables}
    ids_colonnes = {c["id_element"] for c in colonnes if c["id_table"] in visibles}

    champs_par_table: dict[str, list] = {}
    for c in colonnes:
        if c["id_table"] not in visibles:
            continue
        champs_par_table.setdefault(c["id_table"], []).append(_sans_none({
            "id": c["id_element"], "name": c["nom"],
            "type": {"id": c["type_donnee"], "name": c["type_donnee"]},
            "primaryKey": c["cle_primaire"], "unique": c["est_unique"], "nullable": c["nullable"],
            "increment": c["auto_increment"], "characterMaximumLength": c["taille"],
            "precision": c["precision_num"], "scale": c["echelle"], "default": c["valeur_defaut"],
            "collation": c["interclassement"], "comments": c["commentaire"],
            "createdAt": _ms(c["date_creation"]),
        }))

    colonnes_de_index: dict[str, list[str]] = {}
    for ci in colonnes_index:
        if ci["id_colonne"] in ids_colonnes:
            colonnes_de_index.setdefault(ci["id_index"], []).append(ci["id_colonne"])

    index_par_table: dict[str, list] = {}
    for i in index:
        if i["id_table"] not in visibles:
            continue
        index_par_table.setdefault(i["id_table"], []).append(_sans_none({
            "id": i["id_index"], "name": i["nom"], "unique": i["est_unique"],
            "fieldIds": colonnes_de_index.get(i["id_index"], []), "type": i["type_index"],
            "isPrimaryKey": i["est_cle_primaire"], "createdAt": visibles[i["id_table"]],
        }))

    annexes = projet["annexes"] or {}
    cree = _ms(projet["date_creation"])
    return {
        "id": str(projet["id_projet"]),
        "name": projet["nom"],
        "databaseType": projet["type_base"],
        "tables": [
            _sans_none({
                "id": t["id_element"], "name": t["nom"], "schema": t["schema_sql"],
                "x": float(t["position_x"]), "y": float(t["position_y"]),
                "width": None if t["largeur"] is None else float(t["largeur"]),
                "color": t["couleur"], "isView": t["est_vue"], "comments": t["commentaire"],
                "fields": champs_par_table.get(t["id_element"], []),
                "indexes": index_par_table.get(t["id_element"], []),
                "createdAt": visibles[t["id_element"]],
            })
            for t in tables
        ],
        "relationships": [
            {
                "id": r["id_relation"], "name": r["nom"],
                "sourceTableId": r["id_table_source"], "targetTableId": r["id_table_cible"],
                "sourceFieldId": r["id_colonne_source"], "targetFieldId": r["id_colonne_cible"],
                "sourceCardinality": r["cardinalite_source"], "targetCardinality": r["cardinalite_cible"],
                "createdAt": _ms(r["date_creation"]),
            }
            for r in relations
            if r["id_table_source"] in visibles and r["id_table_cible"] in visibles
        ],
        "areas": annexes.get("areas", []),
        "notes": annexes.get("notes", []),
        "customTypes": annexes.get("customTypes", []),
        "dependencies": annexes.get("dependencies", []),
        "createdAt": cree,
        "updatedAt": cree,
    }