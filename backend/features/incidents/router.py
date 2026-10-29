"""Routes HTTP des incidents. Une route par action métier, pour que chaque règle reste explicite et testable.

Aucune logique métier ici : tout passe par `service.py`. Erreurs : 404 (absent), 409 (conflit d'état), 422 (validation).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.incidents import service
from backend.features.incidents.models import IncidentStatus
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCreationRequest,
    IncidentCriticalityChangeRequest,
    IncidentDetailRead,
    IncidentFalsePositiveQualificationRequest,
    IncidentListFilters,
    IncidentRead,
    IncidentStatusChangeRequest,
)

incidents_router = APIRouter(prefix="/incidents", tags=["incidents"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


def read_incident_list_filters(
    statut: Annotated[IncidentStatus | None, Query()] = None,
    criticite_actuelle: Annotated[CriticalityLevel | None, Query()] = None,
    faux_positif: Annotated[bool | None, Query()] = None,
    assigne_a: Annotated[str | None, Query(description="Responsable (égalité exacte)")] = None,
    log_id: Annotated[UUID | None, Query()] = None,
) -> IncidentListFilters:
    """Dépendance FastAPI : lit les filtres de la liste des incidents dans la query string."""
    return IncidentListFilters(
        statut=statut, criticite_actuelle=criticite_actuelle, faux_positif=faux_positif, assigne_a=assigne_a, log_id=log_id
    )


@incidents_router.post("", response_model=IncidentDetailRead, status_code=status.HTTP_201_CREATED)
def create_incident(creation_request: IncidentCreationRequest, database_session: DatabaseSession) -> IncidentDetailRead:
    """Crée un incident à partir d'un log (404 si log absent, 409 si le log a déjà un incident)."""
    return service.create_incident_from_source_log(database_session, creation_request.log_id)


@incidents_router.get("", response_model=PaginatedResponse[IncidentRead])
def list_incidents(
    database_session: DatabaseSession,
    filters: Annotated[IncidentListFilters, Depends(read_incident_list_filters)],
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
) -> PaginatedResponse[IncidentRead]:
    """Liste des incidents, les plus récents d'abord."""
    return service.list_incidents(database_session, filters, pagination)


@incidents_router.get("/{incident_id}", response_model=IncidentDetailRead)
def read_incident(incident_id: UUID, database_session: DatabaseSession) -> IncidentDetailRead:
    """Détail d'un incident, avec la criticité source du log."""
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
