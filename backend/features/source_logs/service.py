"""Règles métier des logs : enregistrement idempotent (interne) et consultation.

Fonctions publiques utilisables par les autres fonctionnalités :
- `store_source_log_if_new` : réservée au futur collecteur ; aucune route HTTP ne l'expose ;
- `fetch_source_log_metadata` : utilisée par `incidents` pour lire la criticité source d'un log.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.domain_errors import ResourceNotFoundError
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.import_runs import service as import_runs_service
from backend.features.source_logs import repository
from backend.features.source_logs.models import SourceLog
from backend.features.source_logs.schemas import (
    NewSourceLogData,
    SourceLogDetailRead,
    SourceLogListFilters,
    SourceLogMetadataRead,
    SourceLogStorageResult,
)


def store_source_log_if_new(database_session: Session, new_source_log: NewSourceLogData) -> SourceLogStorageResult:
    """Enregistre le log s'il est nouveau, sinon retourne l'existant sans le modifier. Valide (commit) la transaction.

    Idempotent : rejouer le même `identifiant_source` (nouvelle tentative, import suivant, collecteur concurrent)
    ne crée jamais de doublon. Le log existant garde son exécution d'origine et sa criticité source.
    Lève ResourceNotFoundError / ResourceConflictError si l'exécution d'import n'existe pas ou est terminée.
    """
    import_runs_service.ensure_import_run_accepts_new_logs(database_session, new_source_log.execution_import_id)

    source_log_values = new_source_log.model_dump()
    source_log_values["criticite_source"] = new_source_log.criticite_source.value
    inserted_source_log_id = repository.insert_source_log_unless_source_identifier_exists(
        database_session, source_log_values
    )
    if inserted_source_log_id is not None:
        database_session.commit()
        return SourceLogStorageResult(source_log_id=inserted_source_log_id, was_inserted=True)

    existing_source_log_id = repository.fetch_source_log_id_by_source_identifier(
        database_session, new_source_log.identifiant_source
    )
    database_session.commit()
    if existing_source_log_id is None:
        # Impossible sauf suppression concurrente du log (aucune route ne le permet) : on le signale plutôt que mentir.
        raise RuntimeError("Conflit d'identifiant source sans log existant : état de la base incohérent.")
    return SourceLogStorageResult(source_log_id=existing_source_log_id, was_inserted=False)


def fetch_source_log_detail(database_session: Session, source_log_id: UUID) -> SourceLogDetailRead:
    """Retourne le détail d'un log (avec `donnees_brutes`). Lève ResourceNotFoundError s'il n'existe pas."""
    return SourceLogDetailRead.model_validate(_fetch_existing_source_log(database_session, source_log_id))


def fetch_source_log_metadata(database_session: Session, source_log_id: UUID) -> SourceLogMetadataRead:
    """Retourne les métadonnées d'un log. Lève ResourceNotFoundError s'il n'existe pas."""
    return SourceLogMetadataRead.model_validate(_fetch_existing_source_log(database_session, source_log_id))


def list_source_logs(
    database_session: Session, filters: SourceLogListFilters, pagination: PaginationParameters
) -> PaginatedResponse[SourceLogMetadataRead]:
    """Retourne une page de métadonnées de logs, événements les plus récents d'abord."""
    filter_values = filters.model_dump()
    if filters.criticite_source is not None:
        filter_values["criticite_source"] = filters.criticite_source.value
    source_logs, total = repository.fetch_source_logs_page(
        database_session, filter_values, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse[SourceLogMetadataRead](
        items=[SourceLogMetadataRead.model_validate(source_log) for source_log in source_logs],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def _fetch_existing_source_log(database_session: Session, source_log_id: UUID) -> SourceLog:
    source_log = repository.fetch_source_log_by_id(database_session, source_log_id)
    if source_log is None:
        raise ResourceNotFoundError(f"Log {source_log_id} introuvable.")
    return source_log
