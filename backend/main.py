"""Point d'entrée de l'API FastAPI.

Pour brancher une nouvelle fonctionnalité : créer son `router.py`, puis l'ajouter avec `application.include_router(...)`
dans `create_application` ci-dessous.

L'interface analyste (`web_interface/`, pages HTML rendues en Python) est servie à la racine ; l'API JSON est
sous `/api` (documentation interactive : `/docs`).
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import get_database_session_factory
from backend.core.http_error_handlers import register_domain_error_handlers
from backend.core.settings import get_application_settings
from backend.features.audit_journal.router import audit_journal_router
from backend.features.dashboard.router import dashboard_router
from backend.features.import_runs.router import import_runs_router
from backend.features.incident_response_settings.router import incident_response_settings_router
from backend.features.incidents.automatic_escalation import run_automatic_escalation_periodically
from backend.features.incidents.router import incidents_router
from backend.features.log_collection.collection_scheduler import run_log_collection_periodically
from backend.features.log_collection.router import log_collection_router
from backend.features.playbooks.router import playbooks_router
from backend.features.source_logs.router import source_logs_router
from web_interface.web_interface_registration import register_web_interface

API_PATH_PREFIX = "/api"


@contextlib.asynccontextmanager
async def run_background_tasks(_application: FastAPI) -> AsyncIterator[None]:
    """Démarre les tâches périodiques activées (escalade, collecte des alertes) et les arrête à l'extinction."""
    settings = get_application_settings()
    background_tasks = []
    if settings.automatic_escalation_interval_seconds > 0:
        background_tasks.append(
            asyncio.create_task(
                run_automatic_escalation_periodically(
                    get_database_session_factory(), settings.automatic_escalation_interval_seconds
                )
            )
        )
    if settings.log_collection_interval_seconds > 0:
        background_tasks.append(
            asyncio.create_task(
                run_log_collection_periodically(get_database_session_factory(), settings.log_collection_interval_seconds)
            )
        )
    yield
    for background_task in background_tasks:
        background_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await background_task


def create_application() -> FastAPI:
    settings = get_application_settings()
    logging.basicConfig(level=settings.log_level)

    application = FastAPI(title="Intelligentsia SOC - Gestion des alertes et incidents", lifespan=run_background_tasks)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_domain_error_handlers(application)
    # ATTENTION : aucune authentification ni autorisation pour l'instant. Ne pas exposer cette API hors d'un poste local.
    # L'API JSON vit sous /api ; la racine est réservée à l'interface web (web_interface/).
    for feature_router in [
        import_runs_router,
        source_logs_router,
        incidents_router,
        playbooks_router,
        incident_response_settings_router,
        audit_journal_router,
        dashboard_router,
        log_collection_router,
    ]:
        application.include_router(feature_router, prefix=API_PATH_PREFIX)

    @application.get(f"{API_PATH_PREFIX}/health", tags=["system"])
    def report_application_health() -> dict[str, str]:
        """Indique que l'API répond (ne teste pas la base)."""
        return {"status": "ok"}

    # Interface web des analystes (pages HTML rendues en Python), après l'API.
    register_web_interface(application, API_PATH_PREFIX)

    return application


application = create_application()
