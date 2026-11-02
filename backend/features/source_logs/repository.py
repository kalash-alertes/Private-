"""Accès base de données pour la table `logs`. Aucune règle métier ici (voir `service.py`)."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.features.source_logs.models import SourceLog


def insert_source_log_unless_source_identifier_exists(
    database_session: Session, source_log_values: dict[str, Any]
) -> UUID | None:
    """Insère le log si son `identifiant_source` est inconnu ; retourne son id, ou None s'il existait déjà.

    Sûr en cas d'imports concurrents : `INSERT ... ON CONFLICT (identifiant_source) DO NOTHING` laisse la base
    arbitrer. Si deux collecteurs insèrent le même log au même moment, un seul réussit, l'autre obtient None,
    sans erreur ni transaction annulée. Une vérification « SELECT puis INSERT » ne garantirait pas cela.
    Le log existant n'est jamais modifié (la criticité source d'origine reste intacte).
    """
    dialect_name = database_session.get_bind().dialect.name
    if dialect_name == "postgresql":
        insert_statement_factory = postgresql_insert
    elif dialect_name == "sqlite":
        insert_statement_factory = sqlite_insert
    else:
        raise NotImplementedError(f"Insertion idempotente non prise en charge pour le dialecte {dialect_name}")

    insert_statement = (
        insert_statement_factory(SourceLog)
        .values(id=uuid4(), **source_log_values)
        .on_conflict_do_nothing(index_elements=[SourceLog.identifiant_source])
        .returning(SourceLog.id)
    )
    return database_session.execute(insert_statement).scalar_one_or_none()


def fetch_source_log_id_by_source_identifier(database_session: Session, identifiant_source: str) -> UUID | None:
    """Retourne l'id du log portant cet identifiant source, ou None."""
    return database_session.scalar(select(SourceLog.id).where(SourceLog.identifiant_source == identifiant_source))


def fetch_source_log_by_id(database_session: Session, source_log_id: UUID) -> SourceLog | None:
    """Retourne le log ou None."""
    return database_session.get(SourceLog, source_log_id)


def fetch_source_logs_by_ids(database_session: Session, source_log_ids: set[UUID]) -> list[SourceLog]:
    """Retourne les logs demandés (en une requête) ; les id inexistants sont ignorés."""
    if not source_log_ids:
        return []
    return list(database_session.scalars(select(SourceLog).where(SourceLog.id.in_(source_log_ids))).all())


def fetch_source_logs_page(
    database_session: Session, filter_values: dict[str, Any], limit: int, offset: int
) -> tuple[list[SourceLog], int]:
    """Retourne une page de logs (événements les plus récents d'abord) et le total correspondant aux filtres.

    `filter_values` : clés de `SourceLogListFilters`, valeurs None ignorées.
    """
    filter_conditions = []
    if filter_values.get("criticite_source") is not None:
        filter_conditions.append(SourceLog.criticite_source == filter_values["criticite_source"])
    if filter_values.get("type") is not None:
        filter_conditions.append(SourceLog.type == filter_values["type"])
    if filter_values.get("execution_import_id") is not None:
        filter_conditions.append(SourceLog.execution_import_id == filter_values["execution_import_id"])
    if filter_values.get("date_evenement_min") is not None:
        filter_conditions.append(SourceLog.date_evenement >= filter_values["date_evenement_min"])
    if filter_values.get("date_evenement_max") is not None:
        filter_conditions.append(SourceLog.date_evenement <= filter_values["date_evenement_max"])

    total = database_session.scalar(select(func.count()).select_from(SourceLog).where(*filter_conditions))
    source_logs = database_session.scalars(
        select(SourceLog)
        .where(*filter_conditions)
        .order_by(SourceLog.date_evenement.desc(), SourceLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(source_logs), total or 0


def count_all_source_logs(database_session: Session) -> int:
    return database_session.scalar(select(func.count()).select_from(SourceLog)) or 0


def fetch_event_dates_between(database_session: Session, start: datetime, end: datetime) -> list[datetime]:
    """Retourne les dates d'événement des logs dans [start, end[ (agrégées ensuite par le service)."""
    return list(
        database_session.scalars(
            select(SourceLog.date_evenement).where(SourceLog.date_evenement >= start, SourceLog.date_evenement < end)
        ).all()
    )
