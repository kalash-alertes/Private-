"""Page « Tableau de bord » (`/`) : indicateurs, activité des alertes, répartition par sévérité, incidents récents."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginationParameters
from backend.features.dashboard import service as dashboard_service
from backend.features.incidents import service as incidents_service
from backend.features.incidents.schemas import IncidentListFilters, IncidentListView
from web_interface.activity_chart_svg import ActivityChartPoint, build_activity_chart_svg
from web_interface.application_layout import build_application_layout_context
from web_interface.display_formatting import CRITICALITY_LEVELS_FROM_MOST_SEVERE
from web_interface.template_rendering import render_page

dashboard_page_router = APIRouter()

RECENT_INCIDENT_COUNT = 8


@dashboard_page_router.get("/", response_class=HTMLResponse)
def show_dashboard_page(
    request: Request, database_session: Annotated[Session, Depends(get_database_session)]
) -> HTMLResponse:
    """Vue d'ensemble : indicateurs clés, graphique des 7 derniers jours, incidents ouverts récents."""
    dashboard = dashboard_service.build_dashboard(database_session)
    recent_open_incidents = incidents_service.list_incidents(
        database_session,
        IncidentListFilters(vue=IncidentListView.IN_PROGRESS),
        PaginationParameters(limit=RECENT_INCIDENT_COUNT, offset=0),
    )
    open_incident_count = dashboard.nombre_incidents_ouverts
    severity_breakdown = [
        {
            "criticality": criticality,
            "count": dashboard.incidents_ouverts_par_criticite.get(criticality, 0),
            "percent": (
                100 * dashboard.incidents_ouverts_par_criticite.get(criticality, 0) / open_incident_count
                if open_incident_count
                else 0
            ),
        }
        for criticality in CRITICALITY_LEVELS_FROM_MOST_SEVERE
    ]
    return render_page(
        request,
        "dashboard.html",
        {
            **build_application_layout_context(
                database_session,
                "tableau_de_bord",
                "Tableau de bord",
                "Vue d'ensemble de votre environnement de réponse aux incidents.",
            ),
            "dashboard": dashboard,
            "activity_chart_svg": build_activity_chart_svg(
                [
                    ActivityChartPoint(day.jour, day.alertes_detectees, day.incidents_traites)
                    for day in dashboard.activite
                ]
            ),
            "severity_breakdown": severity_breakdown,
            "recent_open_incidents": recent_open_incidents,
        },
    )
