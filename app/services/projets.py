"""Création d'un projet (CU 1.1, DRAFTDB-33)."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session


def creer_projet(db: Session, id_utilisateur: UUID, nom: str, description: str | None):
    """Crée un projet vide dont l'utilisateur est le responsable et le concepteur.

    Trois écritures forment un bloc indivisible : le projet, la participation du créateur
    et l'événement du journal (P4). Cette fonction n'appelle pas commit() : c'est la route
    qui valide la transaction, une seule fois, à la fin (dossier, § 5.1.1).

    Le projet est « generic » (RG-11, P5) avec un numéro de séquence à 0 : ces valeurs sont les
    défauts de la table projet. Aucune ligne n'est écrite dans element_schema (RG-08) : un schéma
    vide ne stocke aucun élément.

    Renvoie la ligne du projet créé. Lève 422 si la base refuse une valeur (caractère NUL, par exemple).
    """
    try:
        projet = db.execute(
            text("""INSERT INTO projet (nom, description, id_responsable)
                    VALUES (:nom, :description, :u)
                    RETURNING id_projet, nom, description, type_base, numero_sequence"""),
            {"nom": nom, "description": description, "u": id_utilisateur},
        ).mappings().one()

        # RG-05 : le responsable participe à son projet. RG-06 : au moins un rôle -> concepteur,
        # pour pouvoir modifier le schéma (CU 2.1) dès la création.
        db.execute(
            text("""INSERT INTO participation (id_utilisateur, id_projet, est_concepteur, est_relecteur)
                    VALUES (:u, :p, true, false)"""),
            {"u": id_utilisateur, "p": projet["id_projet"]},
        )

        db.execute(
            text("""INSERT INTO evenement_journal (nature, details, id_utilisateur, id_projet)
                    VALUES ('CREATION_PROJET', :details, :u, :p)""").bindparams(bindparam("details", type_=JSONB)),
            {"details": {"nom": nom}, "u": id_utilisateur, "p": projet["id_projet"]},
        )
    except DataError:  # valeur refusée par PostgreSQL : tout est annulé, rien n'est créé
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Projet refusé : une valeur n'est pas acceptée par la base (caractère NUL, par exemple).",
        )
    return dict(projet)
