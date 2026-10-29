"""Routes HTTP des playbooks (Paramètres > Réponse aux incidents). Aucune logique métier : tout passe par `service.py`."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginatedResponse, PaginationParameters, read_pagination_parameters
from backend.features.playbooks import service
from backend.features.playbooks.schemas import (
    PlaybookDetailRead,
    PlaybookListFilters,
    PlaybookSummaryRead,
    PlaybookWriteRequest,
)

playbooks_router = APIRouter(prefix="/parametres/playbooks", tags=["parametres_playbooks"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


@playbooks_router.post("", response_model=PlaybookDetailRead, status_code=status.HTTP_201_CREATED)
def create_playbook(playbook_request: PlaybookWriteRequest, database_session: DatabaseSession) -> PlaybookDetailRead:
    """Crée un playbook (409 si le nom ou la catégorie est déjà pris)."""
    return service.create_playbook(database_session, playbook_request)


@playbooks_router.get("", response_model=PaginatedResponse[PlaybookSummaryRead])
def list_playbooks(
    database_session: DatabaseSession,
    pagination: Annotated[PaginationParameters, Depends(read_pagination_parameters)],
    categorie: Annotated[str | None, Query(description="Égalité exacte")] = None,
) -> PaginatedResponse[PlaybookSummaryRead]:
    """Liste des playbooks, triés par nom."""
    return service.list_playbooks(database_session, PlaybookListFilters(categorie=categorie), pagination)


@playbooks_router.get("/{playbook_id}", response_model=PlaybookDetailRead)
def read_playbook(playbook_id: UUID, database_session: DatabaseSession) -> PlaybookDetailRead:
    """Détail d'un playbook avec ses étapes ordonnées (404 si absent)."""
    return service.fetch_playbook_detail(database_session, playbook_id)


@playbooks_router.put("/{playbook_id}", response_model=PlaybookDetailRead)
def update_playbook(
    playbook_id: UUID, playbook_request: PlaybookWriteRequest, database_session: DatabaseSession
) -> PlaybookDetailRead:
    """Remplace le playbook et sa liste d'étapes (garder l'`id` d'une étape conserve son suivi dans les incidents)."""
    return service.update_playbook(database_session, playbook_id, playbook_request)


@playbooks_router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playbook(playbook_id: UUID, database_session: DatabaseSession) -> Response:
    """Supprime le playbook ; les incidents qui l'utilisaient n'ont plus de playbook (404 si absent)."""
    service.delete_playbook(database_session, playbook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
