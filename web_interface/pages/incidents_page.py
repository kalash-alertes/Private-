"""Page « Incidents » (`/incidents`) : onglets En cours / Traités, filtres, tableau, création d'un incident.

Colonnes demandées par l'équipe : référence, sévérité, titre, catégorie, statut, alertes, plan, délai, responsable,
mis à jour. Un clic sur une ligne ouvre l'incident sur son playbook (`incident_detail_page.py`).
"""

from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.domain_errors import DomainError
from backend.core.pagination import PaginationParameters
from backend.features.incidents import service as incidents_service
from backend.features.incidents.models import HANDLED_INCIDENT_STATUSES, OPEN_INCIDENT_STATUSES, IncidentStatus
from backend.features.incidents.schemas import IncidentCreationRequest, IncidentListFilters, IncidentListView
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import SourceLogListFilters
from web_interface.application_layout import build_application_layout_context
from web_interface.display_formatting import INCIDENT_STATUS_LABELS
from web_interface.form_values import convert_blank_to_none, describe_action_error
from web_interface.template_rendering import render_page

incidents_page_router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_database_session)]

INCIDENTS_PER_PAGE = 25
# Alertes proposées dans la fenêtre « Nouvel incident » : les plus récentes sans incident.
MAXIMUM_ALERTS_OFFERED_FOR_NEW_INCIDENT = 100


@incidents_page_router.get("/incidents", response_class=HTMLResponse)
def show_incidents_page(
    request: Request,
    database_session: DatabaseSession,
    vue: IncidentListView = IncidentListView.IN_PROGRESS,
    recherche: Annotated[str | None, Query(max_length=255)] = None,
    criticite: CriticalityLevel | None = None,
    statut: IncidentStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    notice: str | None = None,
) -> HTMLResponse:
    """Liste paginée des incidents de l'onglet choisi."""
    return render_incidents_page(
        request, database_session, vue, convert_blank_to_none(recherche), criticite, statut, offset, notice
    )


@incidents_page_router.post("/incidents", response_class=HTMLResponse)
def create_incident_from_form(
    request: Request,
    database_session: DatabaseSession,
    log_id: Annotated[str, Form()],
    titre: Annotated[str, Form()] = "",
    categorie: Annotated[str, Form()] = "",
):
    """Crée un incident à partir d'une alerte puis ouvre sa fiche ; en cas d'erreur, réaffiche la liste avec le motif."""
    try:
        incident = incidents_service.create_incident_from_source_log(
            database_session,
            IncidentCreationRequest(
                log_id=log_id, titre=convert_blank_to_none(titre), categorie=convert_blank_to_none(categorie)
            ),
        )
    except (DomainError, ValidationError) as action_error:
        database_session.rollback()
        return render_incidents_page(
            request,
            database_session,
            IncidentListView.IN_PROGRESS,
            error_message=describe_action_error(action_error),
            status_code=422,
        )
    return RedirectResponse(f"/incidents/{incident.id}?notice=incident_cree", status_code=303)


def render_incidents_page(
    request: Request,
    database_session: Session,
    list_view: IncidentListView,
    search_text: str | None = None,
    criticality: CriticalityLevel | None = None,
    status: IncidentStatus | None = None,
    offset: int = 0,
    notice_key: str | None = None,
    error_message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Construit la page (utilisée aussi pour réafficher la liste après une création refusée)."""
    # Un statut qui n'appartient pas à l'onglet affiché ne donnerait aucun résultat : il est ignoré.
    statuses_of_view = OPEN_INCIDENT_STATUSES if list_view == IncidentListView.IN_PROGRESS else HANDLED_INCIDENT_STATUSES
    if status not in statuses_of_view:
        status = None
    incidents_page = incidents_service.list_incidents(
        database_session,
        IncidentListFilters(vue=list_view, recherche=search_text, criticite_actuelle=criticality, statut=status),
        PaginationParameters(limit=INCIDENTS_PER_PAGE, offset=offset),
    )
    incident_count_by_view = {
        view.value: incidents_service.list_incidents(
            database_session, IncidentListFilters(vue=view), PaginationParameters(limit=1, offset=0)
        ).total
        for view in IncidentListView
    }
    filter_query_values = {
        name: value
        for name, value in {
            "vue": list_view.value,
            "recherche": search_text,
            "criticite": criticality.value if criticality else None,
            "statut": status.value if status else None,
        }.items()
        if value
    }
    return render_page(
        request,
        "incidents.html",
        {
            **build_application_layout_context(
                database_session,
                "incidents",
                "Incidents",
                "Investigation, qualification et suivi des incidents de sécurité.",
                notice_key=notice_key,
                error_message=error_message,
            ),
            "incidents_page": incidents_page,
            "incident_count_by_view": incident_count_by_view,
            "list_view": list_view,
            "search_text": search_text or "",
            "selected_criticality": criticality,
            "selected_status": status,
            "statuses_of_view": [
                (incident_status, INCIDENT_STATUS_LABELS[incident_status])
                for incident_status in IncidentStatus
                if incident_status in statuses_of_view
            ],
            "filter_query": urlencode(filter_query_values),
            "alerts_without_incident": _list_recent_alerts_without_incident(database_session),
        },
        status_code=status_code,
    )


def _list_recent_alerts_without_incident(database_session: Session) -> list:
    recent_alerts = source_logs_service.list_source_logs(
        database_session, SourceLogListFilters(), PaginationParameters(limit=MAXIMUM_ALERTS_OFFERED_FOR_NEW_INCIDENT)
    ).items
    incident_id_by_log_id: dict[UUID, UUID] = incidents_service.fetch_incident_ids_by_log_ids(
        database_session, [alert.id for alert in recent_alerts]
    )
    return [alert for alert in recent_alerts if alert.id not in incident_id_by_log_id]
