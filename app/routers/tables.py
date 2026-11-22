from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.tables import TableAjout, TableAjoutee, TableSupprimee
from app.security import get_current_user
from app.services.acces import charger_projet, exiger_concepteur
from app.services.tables import ajouter_table, supprimer_table

router = APIRouter(tags=["Tables"])


def projet_modifiable(
    id_projet: UUID,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
):
    """Charge le projet en le verrouillant (RG-16), puis exige le rôle de concepteur (RG-06, EX-08).

    C'est une dépendance pour que les droits soient contrôlés avant la validation du corps : l'ordre
    des réponses est 401, 403, puis 422 (dossier, § 4.4.2 et 4.4.11). Le verrou dure jusqu'à la fin
    de la transaction, c'est-à-dire jusqu'au commit() de la route ou à la fermeture de la session.
    """
    projet = charger_projet(db, id_projet, verrouiller=True)
    exiger_concepteur(db, projet, id_utilisateur)
    return projet


@router.post(
    "/projets/{id_projet}/tables",
    status_code=201,
    response_model=TableAjoutee,
    summary="Ajouter une table au schéma du projet (CU 2.1)",
    responses={
        401: {"description": "Utilisateur non identifié"},
        403: {"description": "N'est pas concepteur du projet"},
        404: {"description": "Projet introuvable"},
        422: {"description": "Type de colonne absent ou nom invalide ; nom déjà pris dans le projet (RG-10) ; "
                             "identifiant ChartDB déjà utilisé (P3) ; valeur refusée par la base"},
    },
)
def ajouter(
    table: TableAjout,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
    projet=Depends(projet_modifiable),
):
    """Ajoute la table, ses colonnes et ses index. Une table sans clé primaire est acceptée, avec un avertissement."""
    resultat = ajouter_table(db, projet, id_utilisateur, table)
    db.commit()
    return resultat

@router.delete(
    "/projets/{id_projet}/tables/{id_table}",
    response_model=TableSupprimee,
    summary="Supprimer une table du schéma du projet (CU 2.3)",
    responses={
        401: {"description": "Utilisateur non identifié"},
        403: {"description": "N'est pas concepteur du projet"},
        404: {"description": "Projet ou table introuvable"},
        409: {"description": "Confirmation requise : rien n'est supprimé. detail = "
                             "{code: CONFIRMATION_REQUISE, cles_etrangeres: [...], index: [...]}"},
        422: {"description": "Identifiant de table ou paramètre invalide"},
    },
)
def supprimer(
    id_table: str = Path(min_length=1, max_length=25, description="Identifiant ChartDB de la table"),
    confirme_suppression: bool = False,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
    projet=Depends(projet_modifiable),
):
    """Sans confirmation : liste les liens de la table (409), rien n'est supprimé. Avec confirmation : suppression logique."""
    resultat = supprimer_table(db, projet, id_utilisateur, id_table, confirme_suppression)
    db.commit()
    return resultat