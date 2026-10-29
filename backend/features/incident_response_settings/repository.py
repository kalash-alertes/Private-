"""Accès base de données pour la table `delais_reponse_incidents`. Aucune règle métier ici (voir `service.py`)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.features.incident_response_settings.models import IncidentResponseDeadlineRule


def fetch_all_response_deadline_rules(database_session: Session) -> list[IncidentResponseDeadlineRule]:
    """Retourne toutes les règles (au plus une par criticité)."""
    return list(database_session.scalars(select(IncidentResponseDeadlineRule)).all())


def fetch_response_deadline_rule_by_criticality(
    database_session: Session, criticite: str
) -> IncidentResponseDeadlineRule | None:
    """Retourne la règle de cette criticité, verrouillée pour modification (sans effet sur SQLite), ou None."""
    return database_session.scalars(
        select(IncidentResponseDeadlineRule).where(IncidentResponseDeadlineRule.criticite == criticite).with_for_update()
    ).one_or_none()
