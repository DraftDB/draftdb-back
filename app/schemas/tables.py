"""Ajout d'une table (CU 2.1, DRAFTDB-42) : requête et réponse de POST /api/projets/{id_projet}/tables."""

from pydantic import BaseModel

from app.schemas.chartdb import DBTable
from app.schemas.regles import Avertissement

__all__ = ["Avertissement", "TableAjout", "TableAjoutee", "TableSupprimee"]


class TableAjout(DBTable):
    """Une table au format ChartDB (P1), dont les règles internes sont contrôlées avant toute écriture.

    Les règles qui se voient dans la table elle-même (noms, RG-10 entre colonnes, RG-12, RG-14) sont celles de
    DBTable, communes avec l'import. Ce qui dépend de la base (nom de table libre dans le projet, types admis
    selon le dialecte du projet, identifiants déjà utilisés ou à restaurer) est contrôlé par le service.
    """


class TableAjoutee(BaseModel):
    table: dict  # objet DBTable de ChartDB tel qu'il est enregistré (P1)
    numero_sequence: int
    # Avertissement « table sans clé primaire » seulement (RG-12) : champ conservé pour le front existant.
    avertissement: Avertissement | None  # toujours présent dans la réponse : le client lit la même structure
    # Tous les avertissements non bloquants (EX-05) : clé primaire, mots réservés, noms à protéger.
    avertissements: list[Avertissement]
    # True si la table reprend l'identifiant d'une table supprimée du même projet (annuler, RG-09 précisée).
    restauree: bool


class TableSupprimee(BaseModel):
    """Réponse de DELETE /api/projets/{id_projet}/tables/{id_table} quand la suppression est faite (CU 2.3)."""

    id_table: str
    numero_sequence: int
