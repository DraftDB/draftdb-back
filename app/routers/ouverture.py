from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.projets import ProjetOuvert
from app.security import get_current_user
from app.services.acces import charger_projet, exiger_participant
from app.services.lecture import reconstituer_diagramme

router = APIRouter(tags=["Projets"])


@router.get(
    "/projets/{id_projet}",
    response_model=ProjetOuvert,
    summary="Ouvrir un projet : dernier état du schéma (CU 1.6)",
    responses={
        401: {"description": "Utilisateur non identifié"},
        403: {"description": "L'utilisateur ne participe pas au projet"},
        404: {"description": "Projet introuvable"},
    },
)
def ouvrir_projet(
    id_projet: UUID,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
):
    projet = charger_projet(db, id_projet)
    exiger_participant(db, projet, id_utilisateur)
    return ProjetOuvert(
        id_projet=projet["id_projet"], nom=projet["nom"], description=projet["description"],
        type_base=projet["type_base"], numero_sequence=projet["numero_sequence"],
        diagramme=reconstituer_diagramme(db, projet),
    )