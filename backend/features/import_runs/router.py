"""Routes HTTP de consultation de l'historique des imports. Aucune logique métier : tout passe par `service.py`."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.import_runs import service
from backend.features.import_runs.models import ImportRunStatus
from backend.features.import_runs.schemas import ImportRunListFilters, ImportRunRead

import_runs_router = APIRouter(prefix="/executions-import", tags=["executions_import"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


@import_runs_router.get("", response_model=PaginatedResponse[ImportRunRead])
def list_import_runs(
    database_session: DatabaseSession,
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
    statut: Annotated[ImportRunStatus | None, Query(description="Filtrer par statut")] = None,
) -> PaginatedResponse[ImportRunRead]:
    """Historique des exécutions d'import, les plus récentes d'abord."""
    return service.list_import_runs(database_session, ImportRunListFilters(statut=statut), pagination)


@import_runs_router.get("/{import_run_id}", response_model=ImportRunRead)
def read_import_run(import_run_id: UUID, database_session: DatabaseSession) -> ImportRunRead:
    """Détail d'une exécution d'import (404 si absente)."""
    return service.fetch_import_run(database_session, import_run_id)
