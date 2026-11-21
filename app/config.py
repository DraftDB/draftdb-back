"""Configuration de l'API, lue depuis les variables d'environnement et le fichier .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Le reverse proxy transmet /api/ au serveur (dossier de conception, figure 1).
API_PREFIX = "/api"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    # Taille maximale du dump déclarée par le navigateur (cahier des charges, CU 1.5 : « à fixer »).
    import_taille_max_octets: int = 50 * 1024 * 1024

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()