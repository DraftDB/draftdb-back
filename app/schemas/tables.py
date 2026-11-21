"""Ajout d'une table (CU 2.1, DRAFTDB-42) : requête et réponse de POST /api/projets/{id_projet}/tables."""

from pydantic import BaseModel, model_validator

from app.schemas.chartdb import DBTable


class TableAjout(DBTable):
    """Une table au format ChartDB (P1), dont les règles internes sont contrôlées avant toute écriture.

    Seul ce qui se voit dans la table elle-même est contrôlé ici (RG-10 entre colonnes, RG-12, RG-14).
    Ce qui dépend de la base (nom de table libre dans le projet, identifiants jamais utilisés)
    est contrôlé par le service.
    """

    @model_validator(mode="after")
    def verifier_table(self):
        if not self.name.strip():
            raise ValueError("Le nom de la table est vide.")

        ids_elements = {self.id}  # la table et ses colonnes partagent la même clé primaire en base
        noms_colonnes = set()
        for champ in self.fields:
            if not champ.name.strip():
                raise ValueError(f"Une colonne de la table {self.name!r} a un nom vide.")
            if champ.id in ids_elements:
                raise ValueError(f"Identifiant en double dans la table : {champ.id!r}.")
            ids_elements.add(champ.id)
            if champ.name in noms_colonnes:  # RG-10
                raise ValueError(f"Deux colonnes de la table {self.name!r} portent le nom {champ.name!r} (RG-10).")
            noms_colonnes.add(champ.name)
            if champ.primary_key and champ.nullable:  # RG-12
                raise ValueError(f"La colonne {self.name}.{champ.name} est clé primaire mais nullable (RG-12).")

        ids_colonnes = {champ.id for champ in self.fields}
        ids_index = set()
        for index in self.indexes:
            if index.id in ids_index:
                raise ValueError(f"Identifiant d'index en double : {index.id!r}.")
            ids_index.add(index.id)
            if len(set(index.field_ids)) != len(index.field_ids):  # RG-14
                raise ValueError(f"L'index {index.name!r} cite deux fois la même colonne (RG-14).")
            inconnues = set(index.field_ids) - ids_colonnes
            if inconnues:  # RG-14
                raise ValueError(f"L'index {index.name!r} cite des colonnes absentes de sa table : {sorted(inconnues)}.")
        return self


class Avertissement(BaseModel):
    """Problème non bloquant, renvoyé avec la table (EX-05)."""

    code: str
    message: str


class TableAjoutee(BaseModel):
    table: dict  # objet DBTable de ChartDB tel qu'il est enregistré (P1)
    numero_sequence: int
    avertissement: Avertissement | None  # toujours présent dans la réponse : le client lit la même structure