from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.projets import ProjetCreation, ProjetCree
from app.security import get_current_user
from app.services.projets import creer_projet

router = APIRouter(tags=["Projets"])


@router.post(
    "/projets",
    status_code=201,
    response_model=ProjetCree,
    summary="Créer un projet (CU 1.1)",
    responses={
        401: {"description": "Utilisateur non identifié"},
        422: {"description": "Nom absent ou invalide, description trop longue, valeur refusée par la base"},
    },
)
def creer(
    requete: ProjetCreation,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
):
    """Crée un projet vide ; le créateur en devient le responsable (RG-04) et le concepteur."""
    projet = creer_projet(db, id_utilisateur, requete.nom, requete.description)
    db.commit()
    return projet