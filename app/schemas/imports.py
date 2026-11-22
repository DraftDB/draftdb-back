from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chartdb import Diagramme


class FichierImport(BaseModel):
    """Caractéristiques du fichier : le fichier lui-même n'est jamais envoyé (RG-24)."""

    nom: str = Field(min_length=1, max_length=255)
    dialecte: Literal["mysql", "postgresql"]
    taille_octets: int = Field(ge=0)


class InstructionNonReprise(BaseModel):
    """Ligne, type et raison : jamais le texte de l'instruction, qui pourrait contenir des données (RG-24)."""

    model_config = ConfigDict(extra="forbid")

    ligne: int | None = None
    type: str = Field(max_length=50)
    raison: str = Field(max_length=500)


class RapportImport(BaseModel):
    non_repris: list[InstructionNonReprise] = []


class ImportRequest(BaseModel):
    confirme_remplacement: bool = False
    fichier: FichierImport
    diagramme: Diagramme
    rapport: RapportImport = RapportImport()


class ImportResponse(BaseModel):
    id_import: UUID
    numero_sequence: int
    nb_elements_crees: int