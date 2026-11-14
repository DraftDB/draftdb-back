from fastapi import APIRouter, FastAPI

from app.config import API_PREFIX
from app.routers import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="DraftDB API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    # Toutes les routes sont sous /api. Pour ajouter une route : créer
    # app/routers/<sujet>.py puis l'inclure ici (ex. projets.py pour DRAFTDB-8).
    # C'est aussi ici que se branchera l'authentification (dependencies=[...]).
    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health.router)
    app.include_router(api)
    return app


app = create_app()