"""Fiche d'un incident (`/incidents/{id}`) : son playbook en premier (étapes à cocher), puis informations et actions.

Chaque action est un formulaire POST vers une route dédiée. Succès → redirection vers la fiche avec un message ;
refus (règle métier, validation) → la fiche est réaffichée avec le motif, sans rien modifier.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.domain_errors import DomainError
from backend.core.pagination import MAXIMUM_PAGE_SIZE, PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.schemas import AuditEventListFilters
from backend.features.incidents import incident_playbook_progress
from backend.features.incidents import service as incidents_service
from backend.features.incidents.models import IncidentStatus
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCategoryChangeRequest,
    IncidentCriticalityChangeRequest,
    IncidentFalsePositiveQualificationRequest,
    IncidentPlaybookAssignmentRequest,
    IncidentPlaybookStepCompletionRequest,
    IncidentStatusChangeRequest,
    IncidentTitleChangeRequest,
)
from backend.features.playbooks import service as playbooks_service
from backend.features.playbooks.schemas import PlaybookListFilters
from web_interface.application_layout import build_application_layout_context
from web_interface.display_formatting import INCIDENT_STATUS_LABELS
from web_interface.form_values import convert_blank_to_none, describe_action_error
from web_interface.template_rendering import render_page

incident_detail_page_router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_database_session)]

INCIDENT_HISTORY_EVENT_COUNT = 15


@incident_detail_page_router.get("/incidents/{incident_id}", response_class=HTMLResponse)
def show_incident_detail_page(
    request: Request, incident_id: UUID, database_session: DatabaseSession, notice: str | None = None
) -> HTMLResponse:
    """Fiche de l'incident (404 s'il n'existe pas)."""
    return render_incident_detail_page(request, database_session, incident_id, notice_key=notice)


@incident_detail_page_router.post("/incidents/{incident_id}/statut")
def change_status_from_form(
    request: Request, incident_id: UUID, database_session: DatabaseSession, statut: Annotated[str, Form()]
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incidents_service.change_incident_status(
            database_session, incident_id, IncidentStatusChangeRequest(statut=statut)
        ),
    )


@incident_detail_page_router.post("/incidents/{incident_id}/criticite")
def change_criticality_from_form(
    request: Request, incident_id: UUID, database_session: DatabaseSession, criticite_actuelle: Annotated[str, Form()]
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incidents_service.change_incident_current_criticality(
            database_session, incident_id, IncidentCriticalityChangeRequest(criticite_actuelle=criticite_actuelle)
        ),
    )


@incident_detail_page_router.post("/incidents/{incident_id}/assignation")
def change_assignment_from_form(
    request: Request, incident_id: UUID, database_session: DatabaseSession, assigne_a: Annotated[str, Form()] = ""
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incidents_service.change_incident_assignment(
            database_session, incident_id, IncidentAssignmentRequest(assigne_a=convert_blank_to_none(assigne_a))
        ),
    )


@incident_detail_page_router.post("/incidents/{incident_id}/titre-categorie")
def change_title_and_category_from_form(
    request: Request,
    incident_id: UUID,
    database_session: DatabaseSession,
    titre: Annotated[str, Form()],
    categorie: Annotated[str, Form()],
):
    def change_title_and_category() -> None:
        # Deux actions métier distinctes ; chacune est validée (commit) séparément par son service.
        incidents_service.change_incident_title(database_session, incident_id, IncidentTitleChangeRequest(titre=titre))
        incidents_service.change_incident_category(
            database_session, incident_id, IncidentCategoryChangeRequest(categorie=categorie)
        )

    return _run_incident_action(request, database_session, incident_id, change_title_and_category)


@incident_detail_page_router.post("/incidents/{incident_id}/faux-positif")
def change_false_positive_from_form(
    request: Request,
    incident_id: UUID,
    database_session: DatabaseSession,
    faux_positif: Annotated[str, Form()],
    justification: Annotated[str, Form()] = "",
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incidents_service.change_incident_false_positive_qualification(
            database_session,
            incident_id,
            IncidentFalsePositiveQualificationRequest(
                faux_positif=faux_positif == "oui", justification=convert_blank_to_none(justification)
            ),
        ),
    )


@incident_detail_page_router.post("/incidents/{incident_id}/playbook")
def change_playbook_from_form(
    request: Request, incident_id: UUID, database_session: DatabaseSession, playbook_id: Annotated[str, Form()] = ""
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incidents_service.change_incident_playbook(
            database_session, incident_id, IncidentPlaybookAssignmentRequest(playbook_id=convert_blank_to_none(playbook_id))
        ),
    )


@incident_detail_page_router.post("/incidents/{incident_id}/playbook/etapes/{step_id}")
def change_step_completion_from_form(
    request: Request,
    incident_id: UUID,
    step_id: UUID,
    database_session: DatabaseSession,
    realisee: Annotated[str, Form()],
    realisee_par: Annotated[str, Form()] = "",
):
    return _run_incident_action(
        request,
        database_session,
        incident_id,
        lambda: incident_playbook_progress.change_incident_playbook_step_completion(
            database_session,
            incident_id,
            step_id,
            IncidentPlaybookStepCompletionRequest(
                realisee=realisee == "oui", realisee_par=convert_blank_to_none(realisee_par)
            ),
        ),
        success_notice_key="etape_mise_a_jour",
    )


def render_incident_detail_page(
    request: Request,
    database_session: Session,
    incident_id: UUID,
    notice_key: str | None = None,
    error_message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Construit la fiche. Lève ResourceNotFoundError (→ 404) si l'incident n'existe pas."""
    incident = incidents_service.fetch_incident_detail(database_session, incident_id)
    incident_history = audit_journal_service.list_audit_events(
        database_session,
        AuditEventListFilters(type_ressource="incident", identifiant_ressource=str(incident_id)),
        PaginationParameters(limit=INCIDENT_HISTORY_EVENT_COUNT),
    )
    return render_page(
        request,
        "incident_detail.html",
        {
            **build_application_layout_context(
                database_session,
                "incidents",
                f"{incident.reference} · {incident.titre}",
                "Suivez le playbook de l'incident, qualifiez-le et documentez son traitement.",
                notice_key=notice_key,
                error_message=error_message,
            ),
            "incident": incident,
            "incident_playbook": incident_playbook_progress.fetch_incident_playbook(database_session, incident_id),
            "available_playbooks": playbooks_service.list_playbooks(
                database_session, PlaybookListFilters(), PaginationParameters(limit=MAXIMUM_PAGE_SIZE)
            ).items,
            "incident_statuses": list(INCIDENT_STATUS_LABELS.items()),
            "incident_history": incident_history,
            "is_closed": incident.statut == IncidentStatus.CLOSED,
        },
        status_code=status_code,
    )


def _run_incident_action(
    request: Request,
    database_session: Session,
    incident_id: UUID,
    incident_action: Callable[[], object],
    success_notice_key: str = "incident_modifie",
):
    """Exécute l'action ; succès → redirection vers la fiche, refus → fiche réaffichée avec le motif (code 4xx)."""
    try:
        incident_action()
    except (DomainError, ValidationError) as action_error:
        database_session.rollback()
        return render_incident_detail_page(
            request, database_session, incident_id, error_message=describe_action_error(action_error), status_code=422
        )
    return RedirectResponse(f"/incidents/{incident_id}?notice={success_notice_key}", status_code=303)
