"""Connexion à la base PostgreSQL de l'application.
Le schéma est défini par db/01_schema.sql : l'API utilise les tables existantes,
elle ne les crée pas.
"""

from collections.abc import Iterator
from functools import lru_cache
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête.
    Aucun commit automatique : une route qui écrit appelle db.commit() elle-même,
    ce qui permet de grouper plusieurs écritures dans une seule transaction.
    """
    with Session(get_engine()) as session:
        yield session