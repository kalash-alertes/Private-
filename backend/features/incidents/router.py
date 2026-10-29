"""Routes HTTP des incidents. Une route par action métier, pour que chaque règle reste explicite et testable.

Aucune logique métier ici : tout passe par les services de la fonctionnalité.
Erreurs : 404 (absent), 409 (conflit d'état), 422 (validation ou règle métier).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.incidents import automatic_escalation, incident_playbook_progress, service
from backend.features.incidents.models import IncidentStatus
from backend.features.incidents.schemas import (
    AutomaticEscalationResultRead,
    IncidentAssignmentRequest,
    IncidentCategoryChangeRequest,
    IncidentCreationRequest,
    IncidentCriticalityChangeRequest,
    IncidentDetailRead,
    IncidentFalsePositiveQualificationRequest,
    IncidentListFilters,
    IncidentListItemRead,
    IncidentListView,
    IncidentPlaybookAssignmentRequest,
    IncidentPlaybookRead,
    IncidentPlaybookStepCompletionRequest,
    IncidentStatusChangeRequest,
    IncidentTitleChangeRequest,
)

incidents_router = APIRouter(prefix="/incidents", tags=["incidents"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


def read_incident_list_filters(
    vue: Annotated[IncidentListView | None, Query(description="Onglet : en_cours ou traites")] = None,
    recherche: Annotated[
        str | None, Query(max_length=255, description="Texte cherché dans le titre, la catégorie, le responsable")
    ] = None,
    statut: Annotated[IncidentStatus | None, Query()] = None,
    criticite_actuelle: Annotated[CriticalityLevel | None, Query()] = None,
    faux_positif: Annotated[bool | None, Query()] = None,
    assigne_a: Annotated[str | None, Query(description="Responsable (égalité exacte)")] = None,
    categorie: Annotated[str | None, Query(description="Égalité exacte")] = None,
    playbook_id: Annotated[UUID | None, Query()] = None,
    log_id: Annotated[UUID | None, Query()] = None,
) -> IncidentListFilters:
    """Dépendance FastAPI : lit les filtres de la liste des incidents dans la query string."""
    return IncidentListFilters(
        vue=vue,
        recherche=recherche,
        statut=statut,
        criticite_actuelle=criticite_actuelle,
        faux_positif=faux_positif,
        assigne_a=assigne_a,
        categorie=categorie,
        playbook_id=playbook_id,
        log_id=log_id,
    )


@incidents_router.post("", response_model=IncidentDetailRead, status_code=status.HTTP_201_CREATED)
def create_incident(creation_request: IncidentCreationRequest, database_session: DatabaseSession) -> IncidentDetailRead:
    """Crée un incident à partir d'un log (404 si log absent, 409 si le log a déjà un incident)."""
    return service.create_incident_from_source_log(database_session, creation_request)


@incidents_router.get("", response_model=PaginatedResponse[IncidentListItemRead])
def list_incidents(
    database_session: DatabaseSession,
    filters: Annotated[IncidentListFilters, Depends(read_incident_list_filters)],
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
) -> PaginatedResponse[IncidentListItemRead]:
    """Liste des incidents (référence, sévérité, titre, catégorie, statut, alertes, plan, délai, responsable...)."""
    return service.list_incidents(database_session, filters, pagination)


@incidents_router.post("/escalade-automatique", response_model=AutomaticEscalationResultRead)
def run_automatic_escalation(database_session: DatabaseSession) -> AutomaticEscalationResultRead:
    """Escalade maintenant les incidents ouverts dont le délai est dépassé (si l'escalade est activée)."""
    return automatic_escalation.escalate_overdue_incidents(database_session)


@incidents_router.get("/{incident_id}", response_model=IncidentDetailRead)
def read_incident(incident_id: UUID, database_session: DatabaseSession) -> IncidentDetailRead:
    """Détail d'un incident, avec la criticité source et les alertes d'origine."""
    return service.fetch_incident_detail(database_session, incident_id)


@incidents_router.put("/{incident_id}/statut", response_model=IncidentDetailRead)
def change_incident_status(
    incident_id: UUID, status_change: IncidentStatusChangeRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Change le statut ; `cloture` fixe la date de clôture, quitter `cloture` rouvre l'incident."""
    return service.change_incident_status(database_session, incident_id, status_change)


@incidents_router.put("/{incident_id}/criticite-actuelle", response_model=IncidentDetailRead)
def change_incident_current_criticality(
    incident_id: UUID, criticality_change: IncidentCriticalityChangeRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Réévalue la criticité actuelle (409 si l'incident est clôturé)."""
    return service.change_incident_current_criticality(database_session, incident_id, criticality_change)


@incidents_router.put("/{incident_id}/titre", response_model=IncidentDetailRead)
def change_incident_title(
    incident_id: UUID, title_change: IncidentTitleChangeRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Renomme l'incident (409 si clôturé)."""
    return service.change_incident_title(database_session, incident_id, title_change)


@incidents_router.put("/{incident_id}/categorie", response_model=IncidentDetailRead)
def change_incident_category(
    incident_id: UUID, category_change: IncidentCategoryChangeRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Change la catégorie (409 si clôturé). Ne change pas le playbook."""
    return service.change_incident_category(database_session, incident_id, category_change)


@incidents_router.put("/{incident_id}/faux-positif", response_model=IncidentDetailRead)
def change_incident_false_positive_qualification(
    incident_id: UUID, qualification: IncidentFalsePositiveQualificationRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Qualifie ou retire la qualification de faux positif (justification obligatoire pour qualifier)."""
    return service.change_incident_false_positive_qualification(database_session, incident_id, qualification)


@incidents_router.put("/{incident_id}/assignation", response_model=IncidentDetailRead)
def change_incident_assignment(
    incident_id: UUID, assignment: IncidentAssignmentRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Attribue l'incident ou retire l'attribution (`assigne_a: null`)."""
    return service.change_incident_assignment(database_session, incident_id, assignment)


@incidents_router.get("/{incident_id}/playbook", response_model=IncidentPlaybookRead)
def read_incident_playbook(incident_id: UUID, database_session: DatabaseSession) -> IncidentPlaybookRead:
    """Playbook de l'incident et avancement de chaque étape (`playbook: null` s'il n'en a pas)."""
    return incident_playbook_progress.fetch_incident_playbook(database_session, incident_id)


@incidents_router.put("/{incident_id}/playbook", response_model=IncidentDetailRead)
def change_incident_playbook(
    incident_id: UUID, playbook_assignment: IncidentPlaybookAssignmentRequest, database_session: DatabaseSession
) -> IncidentDetailRead:
    """Attribue un playbook à l'incident ou le retire (`playbook_id: null`) ; 404 si le playbook n'existe pas."""
    return service.change_incident_playbook(database_session, incident_id, playbook_assignment)


@incidents_router.put("/{incident_id}/playbook/etapes/{step_id}", response_model=IncidentPlaybookRead)
def change_incident_playbook_step_completion(
    incident_id: UUID,
    step_id: UUID,
    completion_request: IncidentPlaybookStepCompletionRequest,
    database_session: DatabaseSession,
) -> IncidentPlaybookRead:
    """Coche ou décoche une étape du playbook de l'incident."""
    return incident_playbook_progress.change_incident_playbook_step_completion(
        database_session, incident_id, step_id, completion_request
    )
