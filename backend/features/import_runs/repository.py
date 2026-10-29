"""Accès base de données pour la table `executions_import`. Aucune règle métier ici (voir `service.py`)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.features.import_runs.models import ImportRun


def insert_import_run(database_session: Session) -> ImportRun:
    """Ajoute une exécution `en_cours` (dates fixées par l'horloge de la base) et la retourne après flush."""
    import_run = ImportRun()
    database_session.add(import_run)
    database_session.flush()
    return import_run


def fetch_import_run_by_id(
    database_session: Session, import_run_id: UUID, is_locked_for_update: bool = False
) -> ImportRun | None:
    """Retourne l'exécution ou None.

    `is_locked_for_update` pose un verrou de ligne (SELECT ... FOR UPDATE) jusqu'à la fin de la transaction :
    deux tentatives simultanées de terminer la même exécution sont ainsi sérialisées (sans effet sur SQLite).
    """
    query = select(ImportRun).where(ImportRun.id == import_run_id)
    if is_locked_for_update:
        query = query.with_for_update()
    return database_session.scalars(query).one_or_none()


def fetch_import_runs_page(
    database_session: Session, statut: str | None, limit: int, offset: int
) -> tuple[list[ImportRun], int]:
    """Retourne une page d'exécutions (les plus récentes d'abord) et le nombre total correspondant au filtre."""
    filter_conditions = [ImportRun.statut == statut] if statut is not None else []
    total = database_session.scalar(select(func.count()).select_from(ImportRun).where(*filter_conditions))
    # Tri sur l'id en second critère : ordre stable entre deux pages même si plusieurs exécutions ont le même début.
    import_runs = database_session.scalars(
        select(ImportRun)
        .where(*filter_conditions)
        .order_by(ImportRun.debut.desc(), ImportRun.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(import_runs), total or 0


def fetch_latest_synchronization_cursor(database_session: Session, statuses: list[str]) -> str | None:
    """Retourne le curseur de la plus récente exécution ayant l'un de ces statuts et un curseur, ou None."""
    return database_session.scalar(
        select(ImportRun.curseur_synchronisation)
        .where(ImportRun.statut.in_(statuses), ImportRun.curseur_synchronisation.is_not(None))
        .order_by(ImportRun.debut.desc(), ImportRun.id.desc())
        .limit(1)
    )
