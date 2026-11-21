from uuid import UUID

from pydantic import BaseModel


class ProjetOuvert(BaseModel):
    id_projet: UUID
    nom: str
    description: str | None
    type_base: str
    numero_sequence: int
    diagramme: dict  # objet Diagram de ChartDB (P1)