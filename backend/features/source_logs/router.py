"""Routes HTTP de consultation des logs. Volontairement sans route d'ingestion : seul le collecteur enregistre des logs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, ValidationError
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.source_logs import service
from backend.features.source_logs.schemas import SourceLogDetailRead, SourceLogListFilters, SourceLogMetadataRead

source_logs_router = APIRouter(prefix="/logs", tags=["logs"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


def read_source_log_list_filters(
    criticite_source: Annotated[CriticalityLevel | None, Query()] = None,
    type: Annotated[str | None, Query(description="Type d'événement (égalité exacte)")] = None,
    execution_import_id: Annotated[UUID | None, Query()] = None,
    date_evenement_min: Annotated[AwareDatetime | None, Query(description="Borne incluse, avec fuseau")] = None,
    date_evenement_max: Annotated[AwareDatetime | None, Query(description="Borne incluse, avec fuseau")] = None,
) -> SourceLogListFilters:
    """Dépendance FastAPI : lit les filtres de la query string ; 422 si la plage de dates est inversée."""
    try:
        return SourceLogListFilters(
            criticite_source=criticite_source,
            type=type,
            execution_import_id=execution_import_id,
            date_evenement_min=date_evenement_min,
            date_evenement_max=date_evenement_max,
        )
    except ValidationError as validation_error:
        # Même format de réponse 422 que les autres erreurs de validation FastAPI (sans recopier les valeurs reçues).
        raise RequestValidationError(
            validation_error.errors(include_url=False, include_context=False, include_input=False)
        ) from validation_error


@source_logs_router.get("", response_model=PaginatedResponse[SourceLogMetadataRead])
def list_source_logs(
    database_session: DatabaseSession,
    filters: Annotated[SourceLogListFilters, Depends(read_source_log_list_filters)],
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
) -> PaginatedResponse[SourceLogMetadataRead]:
    """Métadonnées des logs (sans données brutes), événements les plus récents d'abord."""
    return service.list_source_logs(database_session, filters, pagination)


@source_logs_router.get("/{source_log_id}", response_model=SourceLogDetailRead)
def read_source_log(source_log_id: UUID, database_session: DatabaseSession) -> SourceLogDetailRead:
    """Détail d'un log, données brutes comprises (404 si absent)."""
    return service.fetch_source_log_detail(database_session, source_log_id)
