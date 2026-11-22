from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints, field_validator


class ProjetOuvert(BaseModel):
    id_projet: UUID
    nom: str
    description: str | None
    type_base: str
    numero_sequence: int
    diagramme: dict  # objet Diagram de ChartDB (P1)


NomProjet = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
DescriptionProjet = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ProjetCreation(BaseModel):
    """Corps de POST /api/projets (CU 1.1). Le dialecte n'est pas demandé : il est fixé plus tard (P5)."""

    nom: NomProjet
    description: DescriptionProjet | None = None

    @field_validator("description")
    @classmethod
    def description_vide_en_absence(cls, valeur: str | None) -> str | None:
        """Une description vide équivaut à aucune description."""
        return valeur or None


class ProjetCree(BaseModel):
    id_projet: UUID
    nom: str
    description: str | None
    type_base: str  # « generic » à la création (RG-11)
    numero_sequence: int  # 0 : aucune opération pour l'instant