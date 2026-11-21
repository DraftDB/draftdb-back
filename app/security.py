"""Identification de l'utilisateur courant.

Sprint 1 : pas d'authentification. L'identifiant de l'utilisateur est lu dans l'en-tête
X-User-Id (UUID d'un utilisateur existant). Quand le login (CU 0.2) sera développé,
seul le corps de get_current_user changera : les routes qui en dépendent n'auront
pas à être modifiées.
"""

from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


def get_current_user(
    x_user_id: str | None = Header(default=None, description="Provisoire : UUID de l'utilisateur"),
    db: Session = Depends(get_db),
) -> UUID:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Utilisateur non identifié (en-tête X-User-Id manquant).")
    try:
        id_utilisateur = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Identifiant utilisateur invalide.")

    existe = db.execute(
        text("SELECT 1 FROM utilisateur WHERE id_utilisateur = :id"), {"id": id_utilisateur}
    ).first()
    if existe is None:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu.")
    return id_utilisateur