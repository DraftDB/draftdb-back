"""Import du diagramme obtenu par ChartDB à partir d'un dump (CU 1.5, DRAFTDB-40).

Le serveur ne reçoit jamais le dump : seulement le diagramme, les caractéristiques du fichier
et le rapport (RG-24). Tout est enregistré dans une seule transaction.
"""

from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas.chartdb import Diagramme
from app.schemas.imports import ImportRequest, ImportResponse
from app.schemas.regles import Avertissement, avertissements_noms
from app.schemas.types_colonnes import noms_types_personnalises, types_admis, types_inconnus
from app.services.acces import charger_projet, exiger_participant, exiger_responsable


def avertissements_import(diagramme: Diagramme, dialecte: str) -> list[Avertissement]:
    """Avertissements non bloquants de l'import (EX-05) : noms (RG-10) et types (RG-11).

    Un type absent de la liste admise pour le dialecte du dump n'empêche pas l'import (EX-14) : l'analyseur de
    ChartDB a pu garder un type qu'il ne connaît pas (extension PostgreSQL, par exemple). Il est signalé pour être
    corrigé dans l'éditeur. L'avertissement « table sans clé primaire » reste propre à l'ajout (dossier, § 5.6.3).
    """
    admis = types_admis(dialecte, noms_types_personnalises(diagramme.custom_types))
    avertissements = []
    for table in diagramme.tables:
        avertissements += avertissements_noms(table)
        avertissements += [
            Avertissement(
                code="TYPE_INCONNU", id_element=champ.id,
                message=f"Le type {champ.type.id!r} de la colonne {table.name}.{champ.name} n'est pas un type "
                        f"{dialecte} reconnu par DraftDB : à corriger dans l'éditeur (RG-11).",
            )
            for champ in types_inconnus(table.fields, admis)
        ]
    return avertissements


@dataclass
class LignesSchema:
    """Lignes à insérer dans les tables du schéma, une liste de dictionnaires par table."""

    elements: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    colonnes: list[dict] = field(default_factory=list)
    index: list[dict] = field(default_factory=list)
    colonnes_index: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)

    @property
    def nb_elements(self) -> int:
        return len(self.tables) + len(self.colonnes) + len(self.index) + len(self.relations)


def construire_lignes(diagramme: Diagramme, id_projet: UUID) -> LignesSchema:
    """Traduit un diagramme ChartDB en lignes de tables. Fonction pure : aucun accès à la base."""
    lignes = LignesSchema()
    for table in diagramme.tables:
        lignes.elements.append({"id": table.id, "nature": "TABLE", "projet": id_projet})
        lignes.tables.append({
            "id": table.id, "nom": table.name, "schema_sql": table.schema_sql,
            "x": table.x, "y": table.y, "largeur": table.width, "couleur": table.color,
            "commentaire": table.comments, "est_vue": table.is_view,
        })
        for rang, champ in enumerate(table.fields, start=1):  # rang = ordre dans le tableau fields
            lignes.elements.append({"id": champ.id, "nature": "COLONNE", "projet": id_projet})
            lignes.colonnes.append({
                "id": champ.id, "nom": champ.name, "rang": rang, "type_donnee": champ.type.id,
                "taille": champ.character_maximum_length, "precision_num": champ.precision,
                "echelle": champ.scale, "nullable": champ.nullable, "est_unique": champ.unique,
                "cle_primaire": champ.primary_key, "auto_increment": champ.increment,
                "valeur_defaut": champ.default, "interclassement": champ.collation,
                "commentaire": champ.comments, "id_table": table.id,
            })
        for index in table.indexes:
            lignes.index.append({
                "id": index.id, "nom": index.name, "est_unique": index.unique,
                "type_index": index.type, "est_cle_primaire": index.is_primary_key, "id_table": table.id,
            })
            for rang, id_colonne in enumerate(index.field_ids, start=1):
                lignes.colonnes_index.append({"id_index": index.id, "id_colonne": id_colonne, "rang": rang})
    for rel in diagramme.relationships:
        lignes.relations.append({
            "id": rel.id, "nom": rel.name,
            "cardinalite_source": rel.source_cardinality, "cardinalite_cible": rel.target_cardinality,
            "id_colonne_source": rel.source_field_id, "id_colonne_cible": rel.target_field_id,
        })
    return lignes


def annexes_depuis(diagramme: Diagramme) -> dict:
    """Ce qui n'a pas de table dédiée est conservé au format ChartDB dans Projet.annexes."""
    return {
        "areas": diagramme.areas, "notes": diagramme.notes,
        "customTypes": diagramme.custom_types, "dependencies": diagramme.dependencies,
    }


def _inserer(db: Session, sql: str, lignes: list[dict]) -> None:
    if lignes:
        db.execute(text(sql), lignes)


def importer_diagramme(db: Session, id_projet: UUID, id_utilisateur: UUID, requete: ImportRequest) -> ImportResponse:
    projet = charger_projet(db, id_projet, verrouiller=True)  # verrou : un seul import à la fois par projet
    exiger_participant(db, projet, id_utilisateur)
    exiger_responsable(db, projet, id_utilisateur)

    taille_max = get_settings().import_taille_max_octets
    if requete.fichier.taille_octets > taille_max:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {taille_max} octets).")

    nb_tables_existantes = db.execute(
        text("SELECT count(*) FROM element_schema WHERE id_projet = :p AND nature = 'TABLE' AND date_suppression IS NULL"),
        {"p": id_projet},
    ).scalar_one()
    if nb_tables_existantes > 0 and not requete.confirme_remplacement:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFIRMATION_REQUISE", "nb_tables_existantes": nb_tables_existantes},
        )

    diagramme = requete.diagramme
    lignes = construire_lignes(diagramme, id_projet)
    avertissements = avertissements_import(diagramme, requete.fichier.dialecte)
    numero_sequence = projet["numero_sequence"] + 1

    try:
        # Remplacement : suppression logique de l'état précédent, rien n'est effacé (P4).
        db.execute(
            text("UPDATE element_schema SET date_suppression = now() WHERE id_projet = :p AND date_suppression IS NULL"),
            {"p": id_projet},
        )
        _inserer(db, "INSERT INTO element_schema (id_element, nature, id_projet) VALUES (:id, :nature, :projet)", lignes.elements)
        _inserer(db, """INSERT INTO table_schema (id_element, nom, schema_sql, position_x, position_y, largeur, couleur, commentaire, est_vue)
                        VALUES (:id, :nom, :schema_sql, :x, :y, :largeur, :couleur, :commentaire, :est_vue)""", lignes.tables)
        _inserer(db, """INSERT INTO colonne (id_element, nom, rang, type_donnee, taille, precision_num, echelle, nullable, est_unique,
                                             cle_primaire, auto_increment, valeur_defaut, interclassement, commentaire, id_table)
                        VALUES (:id, :nom, :rang, :type_donnee, :taille, :precision_num, :echelle, :nullable, :est_unique,
                                :cle_primaire, :auto_increment, :valeur_defaut, :interclassement, :commentaire, :id_table)""", lignes.colonnes)
        _inserer(db, """INSERT INTO index_schema (id_index, nom, est_unique, type_index, est_cle_primaire, id_table)
                        VALUES (:id, :nom, :est_unique, :type_index, :est_cle_primaire, :id_table)""", lignes.index)
        _inserer(db, "INSERT INTO colonne_index (id_index, id_colonne, rang) VALUES (:id_index, :id_colonne, :rang)", lignes.colonnes_index)
        _inserer(db, """INSERT INTO relation (id_relation, nom, cardinalite_source, cardinalite_cible, id_colonne_source, id_colonne_cible)
                        VALUES (:id, :nom, :cardinalite_source, :cardinalite_cible, :id_colonne_source, :id_colonne_cible)""", lignes.relations)

        db.execute(
            text("UPDATE projet SET annexes = :annexes, type_base = :dialecte, numero_sequence = :seq WHERE id_projet = :p")
            .bindparams(bindparam("annexes", type_=JSONB)),
            {"annexes": annexes_depuis(diagramme), "dialecte": requete.fichier.dialecte, "seq": numero_sequence, "p": id_projet},
        )

        resume = {"tables": len(lignes.tables), "colonnes": len(lignes.colonnes),
                  "index": len(lignes.index), "relations": len(lignes.relations)}
        db.execute(
            text("""INSERT INTO operation (numero_sequence, cible, action, donnees_apres, id_projet, id_auteur)
                    VALUES (:seq, 'projet', 'import', :resume, :p, :u)""").bindparams(bindparam("resume", type_=JSONB)),
            {"seq": numero_sequence, "resume": resume, "p": id_projet, "u": id_utilisateur},
        )
        # L'import ne crée pas de version (dossier, § 4.2.5 et 4.2.9, RG-17) : si le responsable veut figer
        # l'état importé, il crée lui-même une version nommée (CU 3.1). id_version_produite reste donc vide.
        # Le rapport est complété par le serveur (P2) : il compte lui-même les éléments créés.
        rapport = {"elements_crees": resume, "non_repris": [i.model_dump() for i in requete.rapport.non_repris],
                   "avertissements": [a.model_dump() for a in avertissements]}
        id_import = db.execute(
            text(
                """INSERT INTO import_dump (nom_fichier, dialecte, taille_octets, nb_elements_crees, rapport, id_projet,
                                            id_auteur)
                    VALUES (:nom, :dialecte, :taille, :nb, :rapport, :p, :u) RETURNING id_import""")
            .bindparams(bindparam("rapport", type_=JSONB)),
            {"nom": requete.fichier.nom, "dialecte": requete.fichier.dialecte, "taille": requete.fichier.taille_octets,
             "nb": lignes.nb_elements, "rapport": rapport, "p": id_projet, "u": id_utilisateur},
        ).scalar_one()
        db.execute(
            text("""INSERT INTO evenement_journal (nature, details, id_utilisateur, id_projet)
                    VALUES ('IMPORT', :details, :u, :p)""").bindparams(bindparam("details", type_=JSONB)),
            {"details": {"id_import": str(id_import),
                         "nb_elements_crees": lignes.nb_elements, "remplacement": nb_tables_existantes > 0},
             "u": id_utilisateur, "p": id_projet},
        )
        db.commit()
    except (IntegrityError, DataError) as erreur:
        db.rollback()
        if isinstance(erreur, DataError):  # valeur refusée par PostgreSQL, par exemple un caractère NUL
            raise HTTPException(status_code=422, detail="Diagramme refusé : une valeur n'est pas acceptée par la base (caractère NUL, par exemple).")
        contrainte = getattr(getattr(erreur.orig, "diag", None), "constraint_name", None)
        raise HTTPException(
            status_code=422,
            detail=f"Diagramme refusé : identifiant déjà utilisé ou contrainte du schéma violée ({contrainte}).",
        )

    return ImportResponse(id_import=id_import, numero_sequence=numero_sequence, nb_elements_crees=lignes.nb_elements,
                          avertissements=avertissements)
