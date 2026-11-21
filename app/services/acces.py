"""Accès au projet et droits de l'utilisateur (principe P2 : le serveur fait foi)."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def charger_projet(db: Session, id_projet: UUID, *, verrouiller: bool = False):
    """Renvoie la ligne du projet, ou répond 404. verrouiller=True sérialise les écritures du projet."""
    sql = "SELECT * FROM projet WHERE id_projet = :id" + (" FOR UPDATE" if verrouiller else "")
    projet = db.execute(text(sql), {"id": id_projet}).mappings().first()
    if projet is None:
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    return projet


def exiger_participant(db: Session, projet, id_utilisateur: UUID) -> None:
    """403 si l'utilisateur ne participe pas au projet (EX-08). Le responsable est toujours accepté."""
    if projet["id_responsable"] == id_utilisateur:
        return
    participe = db.execute(
        text("SELECT 1 FROM participation WHERE id_utilisateur = :u AND id_projet = :p"),
        {"u": id_utilisateur, "p": projet["id_projet"]},
    ).first()
    if participe is None:
        raise HTTPException(status_code=403, detail="Vous ne participez pas à ce projet.")


def exiger_responsable(db: Session, projet, id_utilisateur: UUID) -> None:
    """403 si l'utilisateur n'est pas le responsable du projet."""
    if projet["id_responsable"] != id_utilisateur:
        raise HTTPException(status_code=403, detail="Seul le responsable du projet peut effectuer cette action.")



def exiger_concepteur(db: Session, projet, id_utilisateur: UUID) -> None:
    """403 si l'utilisateur n'a pas le rôle de concepteur du projet (RG-06, matrice des droits § 2.5, EX-08).

    Le rôle se lit dans participation : qui ne participe pas au projet n'est pas concepteur.
    Le responsable n'est concepteur que s'il a ce rôle, que le CU 1.1 lui donne à la création.
    """
    est_concepteur = db.execute(
        text("SELECT est_concepteur FROM participation WHERE id_utilisateur = :u AND id_projet = :p"),
        {"u": id_utilisateur, "p": projet["id_projet"]},
    ).scalar()
    if not est_concepteur:
        raise HTTPException(status_code=403, detail="Seul un concepteur du projet peut modifier le schéma.")