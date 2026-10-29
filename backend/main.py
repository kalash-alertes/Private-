"""Point d'entrée de l'API FastAPI.

Pour brancher une nouvelle fonctionnalité : créer son `router.py`, puis l'ajouter avec `application.include_router(...)`
dans `create_application` ci-dessous.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.http_error_handlers import register_domain_error_handlers
from backend.core.settings import get_application_settings
from backend.features.import_runs.router import import_runs_router
from backend.features.incidents.router import incidents_router
from backend.features.source_logs.router import source_logs_router


def create_application() -> FastAPI:
    settings = get_application_settings()
    logging.basicConfig(level=settings.log_level)

    application = FastAPI(title="Intelligentsia SOC - Gestion des alertes et incidents")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_domain_error_handlers(application)
    # ATTENTION : aucune authentification ni autorisation pour l'instant. Ne pas exposer cette API hors d'un poste local.
    application.include_router(import_runs_router)
    application.include_router(source_logs_router)
    application.include_router(incidents_router)

    @application.get("/health", tags=["system"])
    def report_application_health() -> dict[str, str]:
        """Indique que l'API répond (ne teste pas la base)."""
        return {"status": "ok"}

    return application


application = create_application()
