"""Accès base de données pour la table `incidents`. Aucune règle métier ici (voir `service.py`)."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.features.incidents.models import Incident


def insert_incident_unless_log_already_has_one(
    database_session: Session, log_id: UUID, criticite_actuelle: str
) -> Incident | None:
    """Insère un incident pour ce log ; retourne None si un incident existe déjà pour ce log.

    Sûr en cas de créations concurrentes : la contrainte UNIQUE sur `log_id` arbitre. L'insertion se fait dans un
    point de sauvegarde (SAVEPOINT) : en cas de violation, seul ce point est annulé et la session reste utilisable.
    Toute autre violation de contrainte est relancée.
    """
    incident = Incident(log_id=log_id, criticite_actuelle=criticite_actuelle)
    try:
        with database_session.begin_nested():
            database_session.add(incident)
            database_session.flush()
    except IntegrityError:
        if fetch_incident_by_log_id(database_session, log_id) is not None:
            return None
        raise
    return incident


def fetch_incident_by_log_id(database_session: Session, log_id: UUID) -> Incident | None:
    """Retourne l'incident lié à ce log, ou None."""
    return database_session.scalars(select(Incident).where(Incident.log_id == log_id)).one_or_none()


def fetch_incident_by_id(
    database_session: Session, incident_id: UUID, is_locked_for_update: bool = False
) -> Incident | None:
    """Retourne l'incident ou None.

    `is_locked_for_update` (SELECT ... FOR UPDATE) sérialise les modifications concurrentes d'un même incident :
    la seconde attend la fin de la première et applique ses règles sur l'état à jour (sans effet sur SQLite).
    """
    query = select(Incident).where(Incident.id == incident_id)
    if is_locked_for_update:
        query = query.with_for_update()
    return database_session.scalars(query).one_or_none()


def fetch_incidents_page(
    database_session: Session, filter_values: dict[str, Any], limit: int, offset: int
) -> tuple[list[Incident], int]:
    """Retourne une page d'incidents (les plus récents d'abord) et le total correspondant aux filtres.

    `filter_values` : clés de `IncidentListFilters` (égalité exacte), valeurs None ignorées.
    """
    filter_conditions = [
        getattr(Incident, column_name) == filter_value
        for column_name, filter_value in filter_values.items()
        if filter_value is not None
    ]
    total = database_session.scalar(select(func.count()).select_from(Incident).where(*filter_conditions))
    incidents = database_session.scalars(
        select(Incident)
        .where(*filter_conditions)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(incidents), total or 0
