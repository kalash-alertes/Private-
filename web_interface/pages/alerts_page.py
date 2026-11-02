"""Page « Alertes » (`/alertes`) : logs importés de FortiAnalyzer (tous niveaux), avec leur incident éventuel.

Les cinq niveaux source sont rangés dans trois cases (ALERT_SEVERITY_GROUP_LEVELS) : Critique = critique + haute,
Moyenne = moyenne, Faible = faible + information. Le niveau source n'est jamais modifié, il reste affiché.

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
from web_interface.alert_charts_svg import AlertSeverityCounts, build_alert_chart_svgs
from web_interface.application_layout import build_application_layout_context
from web_interface.template_rendering import render_page

alerts_page_router = APIRouter()

ALERTS_PER_PAGE = 25
ALERT_SEVERITY_GROUP_LEVELS = {
    "critique": (CriticalityLevel.CRITICAL, CriticalityLevel.HIGH),
    "moyenne": (CriticalityLevel.MEDIUM,),
    "faible": (CriticalityLevel.LOW, CriticalityLevel.INFORMATION),
}


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
    source_alert_counts = {
        criticality: source_logs_service.list_source_logs(
            database_session,
            SourceLogListFilters(criticite_source=criticality),
            PaginationParameters(limit=1),
        ).total
        for criticality in CriticalityLevel
    }
    severity_counts = AlertSeverityCounts(
        critical=sum(source_alert_counts[level] for level in ALERT_SEVERITY_GROUP_LEVELS["critique"]),
        medium=sum(source_alert_counts[level] for level in ALERT_SEVERITY_GROUP_LEVELS["moyenne"]),
        low=sum(source_alert_counts[level] for level in ALERT_SEVERITY_GROUP_LEVELS["faible"]),
    )
    dashboard = dashboard_service.build_dashboard(database_session, activity_day_count=1)
    return render_page(
        request,
        "alerts.html",
        {
            **build_application_layout_context(
                database_session,
                "alertes",
                "Alertes",
                "Visualisez les alertes par niveau de sévérité et créez un incident pour celles qui méritent un traitement.",
            ),
            "alerts_page": alerts_page,
            "incident_id_by_alert_id": incidents_service.fetch_incident_ids_by_log_ids(
                database_session, [alert.id for alert in alerts_page.items]
            ),
            "selected_criticality": criticite,
            "filter_query": urlencode({"criticite": criticite.value} if criticite else {}),
            "severity_counts": severity_counts,
            "alert_charts": build_alert_chart_svgs(severity_counts),
            "alert_counts": {
                "total": dashboard.nombre_alertes,
                "critiques": severity_counts.critical,
                "a_traiter": dashboard.nombre_alertes_a_traiter,
                "traitees": dashboard.nombre_alertes - dashboard.nombre_alertes_a_traiter,
            },
        },
    )
