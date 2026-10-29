"""Accès base de données pour la table `journal_audit`. Aucune règle métier ici (voir `service.py`)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.features.audit_journal.models import AuditEvent


def add_audit_event(database_session: Session, audit_event_values: dict[str, Any]) -> AuditEvent:
    """Ajoute l'événement à la session (sans commit : il sera validé avec la transaction de l'appelant)."""
    audit_event = AuditEvent(**audit_event_values)
    database_session.add(audit_event)
    return audit_event


def fetch_audit_events_page(
    database_session: Session, filter_values: dict[str, Any], limit: int, offset: int
) -> tuple[list[AuditEvent], int]:
    """Retourne une page d'événements (les plus récents d'abord) et le total correspondant aux filtres.

    `filter_values` : clés de `AuditEventListFilters`, valeurs None ignorées.
    """
    filter_conditions = [
        getattr(AuditEvent, column_name) == filter_values[column_name]
        for column_name in ("type_evenement", "acteur", "type_ressource", "identifiant_ressource")
        if filter_values.get(column_name) is not None
    ]
    if filter_values.get("date_evenement_min") is not None:
        filter_conditions.append(AuditEvent.date_evenement >= filter_values["date_evenement_min"])
    if filter_values.get("date_evenement_max") is not None:
        filter_conditions.append(AuditEvent.date_evenement <= filter_values["date_evenement_max"])

    total = database_session.scalar(select(func.count()).select_from(AuditEvent).where(*filter_conditions))
    audit_events = database_session.scalars(
        select(AuditEvent)
        .where(*filter_conditions)
        .order_by(AuditEvent.date_evenement.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(audit_events), total or 0
