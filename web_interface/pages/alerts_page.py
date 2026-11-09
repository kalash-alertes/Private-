"""Page « Alertes » (`/alertes`) : logs importés de FortiAnalyzer (tous niveaux), avec leur incident éventuel.

Les cinq niveaux source sont rangés dans trois cases (ALERT_SEVERITY_GROUP_LEVELS) : Critique = critique + haute,
Moyenne = moyenne, Faible = faible + information. Le niveau source n'est jamais modifié, il reste affiché.

Une alerte sans incident est « à traiter » : un bouton crée l'incident (formulaire vers `POST /incidents`).
"""

from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel, is_at_least_as_severe
from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.core.settings import get_application_settings
from backend.features.dashboard import service as dashboard_service
from backend.features.incidents import service as incidents_service
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import SourceLogListFilters, SourceLogMetadataRead
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


@dataclass(frozen=True)
class AlertTypeGroup:
    """Rubrique dépliable et liens de pagination conservant son type et le filtre courant."""

    type: str
    page: PaginatedResponse[SourceLogMetadataRead]
    query: str


@alerts_page_router.get("/alertes", response_class=HTMLResponse)
def show_alerts_page(
    request: Request,
    database_session: Annotated[Session, Depends(get_database_session)],
    criticite: CriticalityLevel | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    groupe: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> HTMLResponse:
    """Liste des types dépliables, avec pagination indépendante des alertes de chaque type."""
    type_counts = source_logs_service.count_source_logs_by_type(database_session, criticite)
    alert_groups = [
        AlertTypeGroup(
            type=type_count.type,
            page=source_logs_service.list_source_logs(
                database_session,
                SourceLogListFilters(criticite_source=criticite, type=type_count.type),
                PaginationParameters(limit=ALERTS_PER_PAGE, offset=offset if groupe == type_count.type else 0),
            ),
            query=urlencode(
                {"groupe": type_count.type, **({"criticite": criticite.value} if criticite else {})}
            ),
        )
        for type_count in type_counts
    ]
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
    # Seuil de collecte : la case Faible indique « non collectées » quand faible et information sont écartés
    # (défaut `moyenne`), pour qu'un 0 ne soit pas pris pour une panne.
    minimum_collected_criticality = CriticalityLevel(get_application_settings().log_collection_minimum_criticality)
    return render_page(
        request,
        "alerts.html",
        {
            **build_application_layout_context(
                database_session,
                "alertes",
                "Alertes",
                "Déroulez un type pour consulter ses alertes et créer un incident si nécessaire.",
            ),
            "alert_groups": alert_groups,
            "filtered_alert_total": sum(type_count.total for type_count in type_counts),
            "expanded_group": groupe,
            "incident_id_by_alert_id": incidents_service.fetch_incident_ids_by_log_ids(
                database_session, [alert.id for group in alert_groups for alert in group.page.items]
            ),
            "selected_criticality": criticite,
            "severity_counts": severity_counts,
            "minimum_collected_criticality": minimum_collected_criticality,
            "is_low_case_collected": is_at_least_as_severe(CriticalityLevel.LOW, minimum_collected_criticality),
            "alert_charts": build_alert_chart_svgs(severity_counts),
            "alert_counts": {
                "total": dashboard.nombre_alertes,
                "critiques": severity_counts.critical,
                "a_traiter": dashboard.nombre_alertes_a_traiter,
                "traitees": dashboard.nombre_alertes - dashboard.nombre_alertes_a_traiter,
            },
        },
    )


@alerts_page_router.get("/alertes/{source_log_id}", response_class=HTMLResponse)
def show_alert_source_log_page(
    request: Request,
    source_log_id: UUID,
    database_session: Annotated[Session, Depends(get_database_session)],
) -> HTMLResponse:
    """Affiche les données originales conservées du log d'une alerte ; lève ResourceNotFoundError si absent."""
    source_log = source_logs_service.fetch_source_log_detail(database_session, source_log_id)
    return render_page(
        request,
        "alert_source_log.html",
        {
            **build_application_layout_context(
                database_session,
                "alertes",
                "Log original de l'alerte",
                "Les champs d'origine conservés lors de la collecte, sans modification de la criticité source.",
            ),
            "source_log": source_log,
            "incident_id": incidents_service.fetch_incident_ids_by_log_ids(
                database_session, [source_log_id]
            ).get(source_log_id),
        },
    )
