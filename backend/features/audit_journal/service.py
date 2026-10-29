"""Règles du journal d'audit : enregistrement (par les autres fonctionnalités) et consultation.

Fonction publique utilisable par les autres fonctionnalités :
- `record_audit_event` : ajoute un événement à la transaction EN COURS de l'appelant, sans commit. Ainsi, l'événement
  et la modification qu'il décrit sont validés ou annulés ensemble : le journal ne ment jamais sur ce qui a eu lieu.

Le journal ne contient ni secret ni donnée brute de log : les appelants n'y mettent que des descriptions et des
identifiants (ex. pour une connexion échouée, le nom saisi, jamais le mot de passe).
"""

from sqlalchemy.orm import Session

from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.audit_journal import repository
from backend.features.audit_journal.schemas import AuditEventListFilters, AuditEventRead, NewAuditEventData


def record_audit_event(database_session: Session, new_audit_event: NewAuditEventData) -> None:
    """Ajoute l'événement à la session de l'appelant. N'effectue PAS de commit (c'est à l'appelant de le faire)."""
    audit_event_values = new_audit_event.model_dump()
    audit_event_values["type_evenement"] = new_audit_event.type_evenement.value
    repository.add_audit_event(database_session, audit_event_values)


def list_audit_events(
    database_session: Session, filters: AuditEventListFilters, pagination: PaginationParameters
) -> PaginatedResponse[AuditEventRead]:
    """Retourne une page du journal, événements les plus récents d'abord."""
    filter_values = filters.model_dump()
    if filters.type_evenement is not None:
        filter_values["type_evenement"] = filters.type_evenement.value
    audit_events, total = repository.fetch_audit_events_page(
        database_session, filter_values, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse[AuditEventRead](
        items=[AuditEventRead.model_validate(audit_event) for audit_event in audit_events],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )
