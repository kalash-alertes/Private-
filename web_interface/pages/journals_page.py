"""Page « Journaux » (`/journaux`) : source des alertes (démonstration ou FortiAnalyzer), collecte manuelle, et
historique des imports (réussites, échecs, nombres de logs)."""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginationParameters
from backend.core.settings import get_application_settings
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.models import ImportRunStatus
from backend.features.import_runs.schemas import ImportRunListFilters
from backend.features.log_collection import service as log_collection_service
from web_interface.application_layout import build_application_layout_context
from web_interface.display_formatting import IMPORT_RUN_STATUS_LABELS
from web_interface.template_rendering import render_page

journals_page_router = APIRouter()

IMPORT_RUNS_PER_PAGE = 25


@journals_page_router.get("/journaux", response_class=HTMLResponse)
def show_journals_page(
    request: Request,
    database_session: Annotated[Session, Depends(get_database_session)],
    statut: ImportRunStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    notice: str | None = None,
) -> HTMLResponse:
    """Historique paginé des exécutions d'import, les plus récentes d'abord."""
    import_runs_page = import_runs_service.list_import_runs(
        database_session, ImportRunListFilters(statut=statut), PaginationParameters(limit=IMPORT_RUNS_PER_PAGE, offset=offset)
    )
    return render_page(
        request,
        "journals.html",
        {
            **build_application_layout_context(
                database_session,
                "journaux",
                "Journaux",
                "Source des alertes et historique des imports : réussites, échecs et nombre de logs traités.",
                notice_key=notice,
            ),
            "collection_configuration": log_collection_service.describe_collection_configuration(
                get_application_settings()
            ),
            "import_runs_page": import_runs_page,
            "import_run_statuses": list(IMPORT_RUN_STATUS_LABELS.items()),
            "selected_status": statut,
            "filter_query": urlencode({"statut": statut.value} if statut else {}),
        },
    )


@journals_page_router.post("/journaux/collecte")
def run_log_collection_from_page(
    database_session: Annotated[Session, Depends(get_database_session)],
) -> RedirectResponse:
    """Lance une collecte maintenant ; son résultat (réussi ou échoué, avec le motif) apparaît en tête de l'historique."""
    log_collection_service.collect_critical_logs_from_configured_source(database_session)
    return RedirectResponse("/journaux?notice=collecte_executee", status_code=303)
