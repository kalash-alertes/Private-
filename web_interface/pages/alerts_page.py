"""Page « Alertes » (`/alertes`) : logs critiques importés de FortiAnalyzer, avec leur incident éventuel.

Une alerte sans incident est « à traiter » : un bouton crée l'incident (formulaire vers `POST /incidents`).
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.pagination import PaginationParameters
from backend.features.dashboard import service as dashboard_service
from backend.features.incidents import service as incidents_service
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import SourceLogListFilters
from web_interface.application_layout import build_application_layout_context
from web_interface.template_rendering import render_page

alerts_page_router = APIRouter()

ALERTS_PER_PAGE = 25


@alerts_page_router.get("/alertes", response_class=HTMLResponse)
def show_alerts_page(
    request: Request,
    database_session: Annotated[Session, Depends(get_database_session)],
    criticite: CriticalityLevel | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HTMLResponse:
    """Liste paginée des alertes, les plus récentes d'abord."""
    alerts_page = source_logs_service.list_source_logs(
        database_session,
        SourceLogListFilters(criticite_source=criticite),
        PaginationParameters(limit=ALERTS_PER_PAGE, offset=offset),
    )
    critical_alert_count = source_logs_service.list_source_logs(
        database_session, SourceLogListFilters(criticite_source=CriticalityLevel.CRITICAL), PaginationParameters(limit=1)
    ).total
    dashboard = dashboard_service.build_dashboard(database_session, activity_day_count=1)
    return render_page(
        request,
        "alerts.html",
        {
            **build_application_layout_context(
                database_session,
                "alertes",
                "Alertes",
                "Alertes critiques importées de FortiAnalyzer. Créez un incident pour celles qui méritent un traitement.",
            ),
            "alerts_page": alerts_page,
            "incident_id_by_alert_id": incidents_service.fetch_incident_ids_by_log_ids(
                database_session, [alert.id for alert in alerts_page.items]
            ),
            "selected_criticality": criticite,
            "filter_query": urlencode({"criticite": criticite.value} if criticite else {}),
            "alert_counts": {
                "total": dashboard.nombre_alertes,
                "critiques": critical_alert_count,
                "a_traiter": dashboard.nombre_alertes_a_traiter,
                "traitees": dashboard.nombre_alertes - dashboard.nombre_alertes_a_traiter,
            },
        },
    )
