"""Ajout d'une table au schéma d'un projet (CU 2.1, DRAFTDB-42)."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.chartdb import Diagramme
from app.schemas.tables import Avertissement, TableAjout
from app.services.importer import construire_lignes
from app.services.lecture import reconstituer_diagramme


def _verifier_nom_libre(db: Session, id_projet: UUID, table: TableAjout) -> None:
    """RG-10 : deux tables actives d'un même projet ne portent pas le même nom.

    Même règle que l'import : le nom s'apprécie avec le schéma SQL de la table, absent ou vide
    étant équivalents.
    """
    prise = db.execute(
        text("""SELECT 1 FROM table_schema t
                JOIN element_schema e ON e.id_element = t.id_element
                WHERE e.id_projet = :p AND e.date_suppression IS NULL
                  AND t.nom = :nom AND COALESCE(t.schema_sql, '') = :schema"""),
        {"p": id_projet, "nom": table.name, "schema": table.schema_sql or ""},
    ).first()
    if prise is not None:
        raise HTTPException(status_code=422, detail=f"Une table du projet porte déjà le nom {table.name!r} (RG-10).")


def _verifier_identifiants_libres(db: Session, table: TableAjout) -> None:
    """P3 : les identifiants ChartDB sont gardés tels quels, un identifiant déjà utilisé est refusé.

    Les éléments supprimés logiquement comptent : leur identifiant reste en base.
    """
    ids_elements = [table.id, *(champ.id for champ in table.fields)]
    ids_index = [index.id for index in table.indexes]
    utilises = db.execute(
        text("SELECT id_element FROM element_schema WHERE id_element = ANY(:ids)"), {"ids": ids_elements}
    ).scalars().all()
    if ids_index:
        utilises += db.execute(
            text("SELECT id_index FROM index_schema WHERE id_index = ANY(:ids)"), {"ids": ids_index}
        ).scalars().all()
    if utilises:
        raise HTTPException(status_code=422, detail=f"Identifiant ChartDB déjà utilisé : {sorted(utilises)} (P3).")


def _avertissement(table: TableAjout) -> Avertissement | None:
    """EX-05, RG-12 : une table sans clé primaire est acceptée, avec un avertissement."""
    if any(champ.primary_key for champ in table.fields):
        return None
    return Avertissement(
        code="TABLE_SANS_CLE_PRIMAIRE",
        message=f"La table {table.name!r} n'a aucune colonne clé primaire (RG-12).",
    )


def ajouter_table(db: Session, projet, id_utilisateur: UUID, table: TableAjout) -> dict:
    """Ajoute la table, ses colonnes et ses index au schéma du projet, et inscrit l'opération d'ajout.

    `projet` est la ligne du projet, chargée avec verrou et dont le rôle de concepteur de l'utilisateur
    a déjà été contrôlé (routers/tables.py). Les écritures forment un bloc indivisible ; cette fonction
    n'appelle pas commit() : c'est la route qui valide la transaction, une seule fois, à la fin.

    Renvoie la table telle qu'elle est enregistrée, le numéro de séquence de l'opération et l'avertissement.
    """
    id_projet = projet["id_projet"]

    # Même traduction ChartDB -> lignes de tables que l'import (dossier, § 5.5) : le rang d'une
    # colonne est sa position dans fields. construire_lignes ne lit que .tables et .relationships.
    lignes = construire_lignes(Diagramme.model_construct(tables=[table]), id_projet)
    numero_sequence = projet["numero_sequence"] + 1  # le projet est verrouillé : personne d'autre ne le prend (RG-16)
    enregistree = table.model_dump(by_alias=True, exclude_none=True, mode="json")

    try:
        # Les vérifications lisent la base : une valeur qu'elle refuse (NUL) les fait échouer comme une écriture.
        _verifier_nom_libre(db, id_projet, table)
        _verifier_identifiants_libres(db, table)

        db.execute(
            text("INSERT INTO element_schema (id_element, nature, id_projet) VALUES (:id, :nature, :projet)"),
            lignes.elements,
        )
        db.execute(
            text("""INSERT INTO table_schema (id_element, nom, schema_sql, position_x, position_y, largeur, couleur, commentaire, est_vue)
                    VALUES (:id, :nom, :schema_sql, :x, :y, :largeur, :couleur, :commentaire, :est_vue)"""),
            lignes.tables,
        )
        if lignes.colonnes:
            db.execute(
                text("""INSERT INTO colonne (id_element, nom, rang, type_donnee, taille, precision_num, echelle, nullable, est_unique,
                                             cle_primaire, auto_increment, valeur_defaut, interclassement, commentaire, id_table)
                        VALUES (:id, :nom, :rang, :type_donnee, :taille, :precision_num, :echelle, :nullable, :est_unique,
                                :cle_primaire, :auto_increment, :valeur_defaut, :interclassement, :commentaire, :id_table)"""),
                lignes.colonnes,
            )
        if lignes.index:
            db.execute(
                text("""INSERT INTO index_schema (id_index, nom, est_unique, type_index, est_cle_primaire, id_table)
                        VALUES (:id, :nom, :est_unique, :type_index, :est_cle_primaire, :id_table)"""),
                lignes.index,
            )
        if lignes.colonnes_index:
            db.execute(
                text("INSERT INTO colonne_index (id_index, id_colonne, rang) VALUES (:id_index, :id_colonne, :rang)"),
                lignes.colonnes_index,
            )

        db.execute(
            text("UPDATE projet SET numero_sequence = :seq WHERE id_projet = :p"),
            {"seq": numero_sequence, "p": id_projet},
        )
        db.execute(
            text("""INSERT INTO operation (numero_sequence, cible, action, id_entite, donnees_apres, id_projet, id_auteur)
                    VALUES (:seq, 'table', 'ajout', :id_entite, :apres, :p, :u)""")
            .bindparams(bindparam("apres", type_=JSONB)),
            {"seq": numero_sequence, "id_entite": table.id, "apres": enregistree, "p": id_projet, "u": id_utilisateur},
        )
    except (IntegrityError, DataError) as erreur:
        db.rollback()
        if isinstance(erreur, DataError):  # valeur refusée par PostgreSQL, par exemple un caractère NUL
            raise HTTPException(status_code=422, detail="Table refusée : une valeur n'est pas acceptée par la base (caractère NUL, par exemple).")
        contrainte = getattr(getattr(erreur.orig, "diag", None), "constraint_name", None)
        raise HTTPException(
            status_code=422,
            detail=f"Table refusée : identifiant déjà utilisé ou contrainte du schéma violée ({contrainte}).",
        )

    return {"table": enregistree, "numero_sequence": numero_sequence, "avertissement": _avertissement(table)}



def _table_active(db: Session, id_projet: UUID, id_table: str) -> bool:
    """La table figure-t-elle dans le schéma courant du projet (non supprimée) ?"""
    try:
        return db.execute(
            text("""SELECT 1 FROM table_schema t
                    JOIN element_schema e ON e.id_element = t.id_element
                    WHERE t.id_element = :t AND e.id_projet = :p AND e.date_suppression IS NULL"""),
            {"t": id_table, "p": id_projet},
        ).first() is not None
    except DataError:  # identifiant que la base refuse (NUL, par exemple) : aucune table n'en porte un
        db.rollback()
        return False


def _liens_de_la_table(db: Session, id_table: str) -> dict:
    """Clés étrangères et index qui touchent la table (objet métier « Liens de la table », dossier § 4.5.2).

    Les clés étrangères comptent dans les deux sens (la table est la source ou la cible). Une relation dont
    l'autre extrémité est déjà supprimée n'apparaît plus dans le schéma : elle n'est pas listée.
    Les objets reprennent les noms de ChartDB (P1).
    """
    relations = db.execute(
        text("""SELECT r.id_relation, r.nom, cs.id_table AS table_source, cc.id_table AS table_cible,
                       r.id_colonne_source, r.id_colonne_cible
                FROM relation r
                JOIN colonne cs ON cs.id_element = r.id_colonne_source
                JOIN colonne cc ON cc.id_element = r.id_colonne_cible
                JOIN element_schema es ON es.id_element = r.id_colonne_source
                JOIN element_schema ec ON ec.id_element = r.id_colonne_cible
                WHERE es.date_suppression IS NULL AND ec.date_suppression IS NULL
                  AND (cs.id_table = :t OR cc.id_table = :t)
                ORDER BY r.id_relation"""),
        {"t": id_table},
    ).mappings().all()
    index = db.execute(
        text("SELECT id_index, nom FROM index_schema WHERE id_table = :t ORDER BY id_index"), {"t": id_table}
    ).mappings().all()
    return {
        "cles_etrangeres": [
            {"id": r["id_relation"], "name": r["nom"], "sourceTableId": r["table_source"], "targetTableId": r["table_cible"],
             "sourceFieldId": r["id_colonne_source"], "targetFieldId": r["id_colonne_cible"]}
            for r in relations
        ],
        "index": [{"id": i["id_index"], "name": i["nom"]} for i in index],
    }


def supprimer_table(db: Session, projet, id_utilisateur: UUID, id_table: str, confirme_suppression: bool) -> dict:
    """Supprime logiquement la table et ses colonnes (RG-15, P4), après confirmation du concepteur.

    `projet` est la ligne du projet, chargée avec verrou et dont le rôle de concepteur de l'utilisateur
    a déjà été contrôlé (routers/tables.py). Sans confirmation, rien n'est écrit : le 409 liste les liens
    de la table. Avec confirmation, la suppression, le numéro de séquence et l'opération forment un bloc
    indivisible ; cette fonction n'appelle pas commit() : c'est la route qui valide, une seule fois.

    Les relations et les index liés ne sont pas touchés : ils disparaissent du schéma courant avec leur
    table ou leur colonne (dossier, § 5.7), ce que la lecture du projet fait déjà.
    """
    id_projet = projet["id_projet"]
    if not _table_active(db, id_projet, id_table):
        raise HTTPException(status_code=404, detail="Table introuvable dans ce projet.")

    liens = _liens_de_la_table(db, id_table)
    if not confirme_suppression:  # la confirmation est exigée à chaque suppression, même sans lien (diagramme, fig. 34)
        raise HTTPException(status_code=409, detail={"code": "CONFIRMATION_REQUISE", **liens})

    # État avant : la table au format ChartDB, comme l'ajout l'a enregistrée, pour pouvoir la restituer (RG-16).
    avant = next(t for t in reconstituer_diagramme(db, projet)["tables"] if t["id"] == id_table)
    numero_sequence = projet["numero_sequence"] + 1  # le projet est verrouillé : personne d'autre ne le prend (RG-16)

    try:
        # Les colonnes déjà supprimées gardent leur date d'origine.
        db.execute(
            text("""UPDATE element_schema SET date_suppression = now()
                    WHERE date_suppression IS NULL
                      AND (id_element = :t OR id_element IN (SELECT id_element FROM colonne WHERE id_table = :t))"""),
            {"t": id_table},
        )
        db.execute(
            text("UPDATE projet SET numero_sequence = :seq WHERE id_projet = :p"),
            {"seq": numero_sequence, "p": id_projet},
        )
        db.execute(
            text("""INSERT INTO operation (numero_sequence, cible, action, id_entite, donnees_avant, id_projet, id_auteur)
                    VALUES (:seq, 'table', 'suppression', :id_entite, :avant, :p, :u)""")
            .bindparams(bindparam("avant", type_=JSONB)),
            {"seq": numero_sequence, "id_entite": id_table, "avant": avant, "p": id_projet, "u": id_utilisateur},
        )
    except SQLAlchemyError:  # échec technique : tout est annulé, l'état précédent reste intact (dossier, § 4.5.11)
        db.rollback()
        raise

    return {"id_table": id_table, "numero_sequence": numero_sequence}