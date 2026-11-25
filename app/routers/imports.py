from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.imports import ImportRequest, ImportResponse
from app.security import get_current_user
from app.services.importer import importer_diagramme

router = APIRouter(tags=["Import de dump"])


@router.post(
    "/projets/{id_projet}/import",
    status_code=201,
    response_model=ImportResponse,
    summary="Importer le diagramme obtenu à partir d'un dump (CU 1.5)",
    responses={
        401: {"description": "Utilisateur non identifié"},
        403: {"description": "Pas participant, ou participant non responsable"},
        404: {"description": "Projet introuvable"},
        409: {"description": "Schéma non vide : confirmation requise (confirme_remplacement)"},
        413: {"description": "Fichier trop volumineux"},
        422: {"description": "Diagramme ou requête invalide"},
    },
)
def importer_dump(
    id_projet: UUID,
    requete: ImportRequest,
    db: Session = Depends(get_db),
    id_utilisateur: UUID = Depends(get_current_user),
):
    return importer_diagramme(db, id_projet, id_utilisateur, requete)