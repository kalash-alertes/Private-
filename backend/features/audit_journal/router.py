"""Routes HTTP du journal d'audit (Paramètres > Journal d'audit). Lecture seule : aucune route d'écriture.

Aucune logique métier ici : tout passe par `service.py`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, ValidationError
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.audit_journal import service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import AuditEventListFilters, AuditEventRead

audit_journal_router = APIRouter(prefix="/parametres/journal-audit", tags=["parametres_journal_audit"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


def read_audit_event_list_filters(
    type_evenement: Annotated[AuditEventType | None, Query()] = None,
    acteur: Annotated[str | None, Query(description="Égalité exacte")] = None,
    type_ressource: Annotated[str | None, Query(description="Ex. incident, playbook")] = None,
    identifiant_ressource: Annotated[str | None, Query()] = None,
    date_evenement_min: Annotated[AwareDatetime | None, Query(description="Borne incluse, avec fuseau")] = None,
    date_evenement_max: Annotated[AwareDatetime | None, Query(description="Borne incluse, avec fuseau")] = None,
) -> AuditEventListFilters:
    """Dépendance FastAPI : lit les filtres de la query string ; 422 si la plage de dates est inversée."""
    try:
        return AuditEventListFilters(
            type_evenement=type_evenement,
            acteur=acteur,
            type_ressource=type_ressource,
            identifiant_ressource=identifiant_ressource,
            date_evenement_min=date_evenement_min,
            date_evenement_max=date_evenement_max,
        )
    except ValidationError as validation_error:
        raise RequestValidationError(
            validation_error.errors(include_url=False, include_context=False, include_input=False)
        ) from validation_error


@audit_journal_router.get("", response_model=PaginatedResponse[AuditEventRead])
def list_audit_events(
    database_session: DatabaseSession,
    filters: Annotated[AuditEventListFilters, Depends(read_audit_event_list_filters)],
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
) -> PaginatedResponse[AuditEventRead]:
    """Journal d'audit, événements les plus récents d'abord."""
    return service.list_audit_events(database_session, filters, pagination)
