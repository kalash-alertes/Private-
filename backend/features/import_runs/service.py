"""Règles métier de l'historique des imports : démarrer, terminer et consulter une exécution de collecte.

Fonctions publiques utilisables par les autres fonctionnalités (futur collecteur, `source_logs`) :
`start_import_run`, `finish_import_run`, `ensure_import_run_accepts_new_logs`, `fetch_import_run`.

Il n'existe volontairement aucune route HTTP pour démarrer ou terminer une exécution : seul le collecteur
(code interne) le fait. Les routes exposent uniquement la consultation.
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.import_runs import repository
from backend.features.import_runs.error_message_sanitizer import sanitize_import_error_message
from backend.features.import_runs.models import ImportRun, ImportRunStatus
from backend.features.import_runs.schemas import ImportRunFinishedOutcome, ImportRunListFilters, ImportRunRead


def start_import_run(database_session: Session) -> ImportRunRead:
    """Crée et valide (commit) une exécution `en_cours`. Retourne l'exécution créée."""
    import_run = repository.insert_import_run(database_session)
    database_session.commit()
    database_session.refresh(import_run)
    return ImportRunRead.model_validate(import_run)


def finish_import_run(
    database_session: Session, import_run_id: UUID, finished_outcome: ImportRunFinishedOutcome
) -> ImportRunRead:
    """Termine une exécution `en_cours` avec son statut final, ses compteurs et son erreur éventuelle.

    Le message d'erreur est nettoyé (secrets masqués, longueur limitée) avant enregistrement.
    Lève ResourceNotFoundError si l'exécution n'existe pas, ResourceConflictError si elle est déjà terminée
    (une exécution terminée n'est jamais réécrite : son historique doit rester fiable).
    """
    import_run = _fetch_existing_import_run(database_session, import_run_id, is_locked_for_update=True)
    if import_run.statut != ImportRunStatus.IN_PROGRESS:
        raise ResourceConflictError(f"L'exécution d'import {import_run_id} est déjà terminée ({import_run.statut}).")

    import_run.statut = finished_outcome.statut.value
    import_run.nb_logs_recus = finished_outcome.nb_logs_recus
    import_run.nb_logs_inseres = finished_outcome.nb_logs_inseres
    import_run.nb_logs_ignores = finished_outcome.nb_logs_ignores
    import_run.erreur = sanitize_import_error_message(finished_outcome.erreur) if finished_outcome.erreur else None
    import_run.curseur_synchronisation = finished_outcome.curseur_synchronisation
    # Horloge de la base (comme `debut`) : évite qu'un décalage d'horloge applicative donne fin < debut.
    import_run.fin = func.now()
    database_session.commit()
    database_session.refresh(import_run)
    return ImportRunRead.model_validate(import_run)


def ensure_import_run_accepts_new_logs(database_session: Session, import_run_id: UUID) -> None:
    """Vérifie qu'on peut rattacher de nouveaux logs à cette exécution (elle existe et est `en_cours`).

    Lève ResourceNotFoundError ou ResourceConflictError. Garantit que les compteurs d'une exécution terminée
    ne sont plus contredits par des logs ajoutés après coup.
    """
    import_run = _fetch_existing_import_run(database_session, import_run_id)
    if import_run.statut != ImportRunStatus.IN_PROGRESS:
        raise ResourceConflictError(
            f"L'exécution d'import {import_run_id} est terminée : aucun log ne peut plus lui être rattaché."
        )


def fetch_import_run(database_session: Session, import_run_id: UUID) -> ImportRunRead:
    """Retourne une exécution. Lève ResourceNotFoundError si elle n'existe pas."""
    return ImportRunRead.model_validate(_fetch_existing_import_run(database_session, import_run_id))


def list_import_runs(
    database_session: Session, filters: ImportRunListFilters, pagination: PaginationParameters
) -> PaginatedResponse[ImportRunRead]:
    """Retourne une page de l'historique des imports, les plus récents d'abord."""
    import_runs, total = repository.fetch_import_runs_page(
        database_session,
        statut=filters.statut.value if filters.statut else None,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse[ImportRunRead](
        items=[ImportRunRead.model_validate(import_run) for import_run in import_runs],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def _fetch_existing_import_run(
    database_session: Session, import_run_id: UUID, is_locked_for_update: bool = False
) -> ImportRun:
    import_run = repository.fetch_import_run_by_id(database_session, import_run_id, is_locked_for_update)
    if import_run is None:
        raise ResourceNotFoundError(f"Exécution d'import {import_run_id} introuvable.")
    return import_run
