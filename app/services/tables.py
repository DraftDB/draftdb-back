"""Ajout (CU 2.1, DRAFTDB-42) et suppression (CU 2.3, DRAFTDB-43) d'une table du schéma d'un projet."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.chartdb import Diagramme
from app.schemas.regles import avertissement_cle_primaire, avertissements_table
from app.schemas.tables import TableAjout
from app.schemas.types_colonnes import noms_types_personnalises, types_admis, types_inconnus
from app.services.importer import construire_lignes
from app.services.lecture import reconstituer_diagramme

_INSERER_ELEMENT = "INSERT INTO element_schema (id_element, nature, id_projet) VALUES (:id, :nature, :projet)"
_INSERER_COLONNE = """INSERT INTO colonne (id_element, nom, rang, type_donnee, taille, precision_num, echelle, nullable,
                                           est_unique, cle_primaire, auto_increment, valeur_defaut, interclassement,
                                           commentaire, id_table)
                      VALUES (:id, :nom, :rang, :type_donnee, :taille, :precision_num, :echelle, :nullable, :est_unique,
                              :cle_primaire, :auto_increment, :valeur_defaut, :interclassement, :commentaire, :id_table)"""
_INSERER_INDEX = """INSERT INTO index_schema (id_index, nom, est_unique, type_index, est_cle_primaire, id_table)
                    VALUES (:id, :nom, :est_unique, :type_index, :est_cle_primaire, :id_table)"""
_INSERER_COLONNE_INDEX = "INSERT INTO colonne_index (id_index, id_colonne, rang) VALUES (:id_index, :id_colonne, :rang)"


def _executer(db: Session, sql: str, lignes: list[dict]) -> None:
    if lignes:
        db.execute(text(sql), lignes)


def _verifier_nom_libre(db: Session, id_projet: UUID, table: TableAjout) -> None:
    """RG-10 : deux tables actives d'un même projet ne portent pas le même nom, sans tenir compte de la casse.

    Même règle que l'import : le nom s'apprécie avec le schéma SQL de la table, absent ou vide
    étant équivalents. « Client » et « client » sont la même table pour PostgreSQL et pour MySQL
    sous Windows et macOS.
    """
    prise = db.execute(
        text("""SELECT 1 FROM table_schema t
                JOIN element_schema e ON e.id_element = t.id_element
                WHERE e.id_projet = :p AND e.date_suppression IS NULL
                  AND lower(t.nom) = lower(:nom) AND lower(COALESCE(t.schema_sql, '')) = lower(:schema)"""),
        {"p": id_projet, "nom": table.name, "schema": table.schema_sql or ""},
    ).first()
    if prise is not None:
        raise HTTPException(status_code=422, detail=f"Une table du projet porte déjà le nom {table.name!r} "
                                                    "(sans tenir compte de la casse, RG-10).")


def _verifier_types(projet, table: TableAjout) -> None:
    """CU 2.1 étape 3, RG-11 : le type de chaque colonne est choisi dans la liste admise pour le dialecte du projet.

    Projet « generic » : types génériques de ChartDB ; projet « mysql » ou « postgresql » : en plus, les types
    du dialecte. Les types personnalisés du projet (annexes.customTypes) sont toujours admis.
    """
    admis = types_admis(projet["type_base"], noms_types_personnalises((projet["annexes"] or {}).get("customTypes")))
    inconnus = types_inconnus(table.fields, admis)
    if inconnus:
        liste = ", ".join(f"{champ.name} : {champ.type.id!r}" for champ in inconnus)
        raise HTTPException(
            status_code=422,
            detail=f"Type de colonne non reconnu pour un projet « {projet['type_base']} » ({liste}) (RG-11).",
        )


def _restauration(db: Session, id_projet: UUID, table: TableAjout) -> bool:
    """P3 et RG-09 précisée : un identifiant ChartDB déjà utilisé est refusé, sauf pour restaurer une table supprimée.

    Renvoie True si la table reprend l'identifiant d'une table supprimée logiquement **du même projet** (annuler
    une suppression, par exemple). Ses colonnes et ses index peuvent alors reprendre leurs anciens identifiants ;
    tout autre identifiant déjà présent en base (élément actif, autre projet, autre table) est refusé (422).
    """
    existants = {
        r["id_element"]: r
        for r in db.execute(
            text("""SELECT e.id_element, e.nature, e.id_projet, e.date_suppression, c.id_table
                    FROM element_schema e LEFT JOIN colonne c ON c.id_element = e.id_element
                    WHERE e.id_element = ANY(:ids)"""),
            {"ids": [table.id, *(champ.id for champ in table.fields)]},
        ).mappings()
    }
    ancienne = existants.get(table.id)
    restauration = (
        ancienne is not None and ancienne["nature"] == "TABLE"
        and ancienne["id_projet"] == id_projet and ancienne["date_suppression"] is not None
    )
    refuses = [] if ancienne is None or restauration else [table.id]
    for champ in table.fields:
        colonne = existants.get(champ.id)
        if colonne is not None and not (
            restauration and colonne["nature"] == "COLONNE" and colonne["id_table"] == table.id
            and colonne["date_suppression"] is not None
        ):
            refuses.append(champ.id)
    ids_index = [index.id for index in table.indexes]
    if ids_index:
        for id_index, id_table in db.execute(
            text("SELECT id_index, id_table FROM index_schema WHERE id_index = ANY(:ids)"), {"ids": ids_index}
        ).all():
            if not (restauration and id_table == table.id):
                refuses.append(id_index)
    if refuses:
        raise HTTPException(
            status_code=422,
            detail=f"Identifiant ChartDB déjà utilisé : {sorted(refuses)} (P3). Seule une table supprimée de ce projet "
                   "peut être restaurée, avec ses propres colonnes et index (RG-09).",
        )
    return restauration


def _inserer(db: Session, lignes) -> None:
    """Nouvelle table : la table, ses colonnes et ses index sont insérés."""
    _executer(db, _INSERER_ELEMENT, lignes.elements)
    _executer(db, """INSERT INTO table_schema (id_element, nom, schema_sql, position_x, position_y, largeur, couleur,
                                               commentaire, est_vue)
                     VALUES (:id, :nom, :schema_sql, :x, :y, :largeur, :couleur, :commentaire, :est_vue)""", lignes.tables)
    _executer(db, _INSERER_COLONNE, lignes.colonnes)
    _executer(db, _INSERER_INDEX, lignes.index)
    _executer(db, _INSERER_COLONNE_INDEX, lignes.colonnes_index)


def _restaurer(db: Session, id_table: str, lignes) -> None:
    """Table supprimée reprise (RG-09, RG-15 précisées) : le corps reçu devient l'état de la table.

    - La table et les colonnes reprises redeviennent actives (date_suppression vidée) et prennent les valeurs reçues ;
      les colonnes nouvelles sont insérées ; les anciennes colonnes absentes du corps restent supprimées.
    - Les index reçus remplacent ceux de l'ancienne table. Les anciens index absents du corps sont retirés : un index
      n'a pas d'historique propre, son état passé reste dans l'opération de suppression de la table (donnees_avant).
    - Les relations ne sont pas dans le corps : celles dont les deux colonnes sont de nouveau actives réapparaissent,
      ce qui est le comportement attendu d'une annulation.
    """
    ids_colonnes = [c["id"] for c in lignes.colonnes]
    reprises = set(db.execute(
        text("SELECT id_element FROM colonne WHERE id_table = :t AND id_element = ANY(:ids)"),
        {"t": id_table, "ids": ids_colonnes},
    ).scalars())
    db.execute(
        text("UPDATE element_schema SET date_suppression = NULL WHERE id_element = ANY(:ids)"),
        {"ids": [id_table, *reprises]},
    )
    _executer(db, """UPDATE table_schema SET nom = :nom, schema_sql = :schema_sql, position_x = :x, position_y = :y,
                            largeur = :largeur, couleur = :couleur, commentaire = :commentaire, est_vue = :est_vue
                     WHERE id_element = :id""", lignes.tables)
    _executer(db, """UPDATE colonne SET nom = :nom, rang = :rang, type_donnee = :type_donnee, taille = :taille,
                            precision_num = :precision_num, echelle = :echelle, nullable = :nullable,
                            est_unique = :est_unique, cle_primaire = :cle_primaire, auto_increment = :auto_increment,
                            valeur_defaut = :valeur_defaut, interclassement = :interclassement,
                            commentaire = :commentaire
                     WHERE id_element = :id""", [c for c in lignes.colonnes if c["id"] in reprises])
    _executer(db, _INSERER_ELEMENT, [e for e in lignes.elements if e["nature"] == "COLONNE" and e["id"] not in reprises])
    _executer(db, _INSERER_COLONNE, [c for c in lignes.colonnes if c["id"] not in reprises])

    ids_index = [i["id"] for i in lignes.index]
    db.execute(  # anciens index absents du corps (colonne_index suit par ON DELETE CASCADE)
        text("DELETE FROM index_schema WHERE id_table = :t AND NOT (id_index = ANY(:ids))"),
        {"t": id_table, "ids": ids_index},
    )
    anciens = set(db.execute(
        text("SELECT id_index FROM index_schema WHERE id_table = :t"), {"t": id_table}
    ).scalars())
    if anciens:
        db.execute(text("DELETE FROM colonne_index WHERE id_index = ANY(:ids)"), {"ids": list(anciens)})
    _executer(db, """UPDATE index_schema SET nom = :nom, est_unique = :est_unique, type_index = :type_index,
                            est_cle_primaire = :est_cle_primaire
                     WHERE id_index = :id""", [i for i in lignes.index if i["id"] in anciens])
    _executer(db, _INSERER_INDEX, [i for i in lignes.index if i["id"] not in anciens])
    _executer(db, _INSERER_COLONNE_INDEX, lignes.colonnes_index)


def ajouter_table(db: Session, projet, id_utilisateur: UUID, table: TableAjout) -> dict:
    """Ajoute la table, ses colonnes et ses index au schéma du projet, et inscrit l'opération d'ajout.

    `projet` est la ligne du projet, chargée avec verrou et dont le rôle de concepteur de l'utilisateur
    a déjà été contrôlé (routers/tables.py). Les écritures forment un bloc indivisible ; cette fonction
    n'appelle pas commit() : c'est la route qui valide la transaction, une seule fois, à la fin.

    Si la table reprend l'identifiant d'une table supprimée du même projet, elle est restaurée (RG-09 précisée).

    Renvoie la table telle qu'elle est enregistrée, le numéro de séquence de l'opération, les avertissements
    et l'indication de restauration.
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
        _verifier_types(projet, table)
        restauree = _restauration(db, id_projet, table)

        if restauree:
            _restaurer(db, table.id, lignes)
        else:
            _inserer(db, lignes)

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

    return {
        "table": enregistree, "numero_sequence": numero_sequence,
        "avertissement": avertissement_cle_primaire(table), "avertissements": avertissements_table(table),
        "restauree": restauree,
    }


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