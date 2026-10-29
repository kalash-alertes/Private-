"""Indicateurs d'incidents pour le tableau de bord.

- incidents ouverts / traités, et répartition des ouverts par criticité actuelle ;
- incidents ouverts dont le délai de traitement est dépassé (même calcul que la liste, cf. `incident_views.py`) ;
- temps moyen de traitement = moyenne de (`traite_le` - `created_at`) sur les incidents traités ;
- incidents traités par jour (UTC) sur la période demandée.

Calculs en Python sur les incidents concernés : identique sur PostgreSQL et SQLite, suffisant pour les volumes V1.
Si les volumes augmentent, passer ces agrégations en SQL.
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import interpret_stored_datetime_as_utc
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incidents import repository
from backend.features.incidents.incident_views import compute_processing_deadline
from backend.features.incidents.models import HANDLED_INCIDENT_STATUSES, OPEN_INCIDENT_STATUSES
from backend.features.incidents.schemas import IncidentStatisticsRead


def compute_incident_statistics(database_session: Session, first_day: date, last_day: date) -> IncidentStatisticsRead:
    """Retourne les indicateurs d'incidents ; `incidents_traites_par_jour` couvre [first_day, last_day] (0 compris)."""
    open_incidents = repository.fetch_incidents_with_statuses(
        database_session, [status.value for status in OPEN_INCIDENT_STATUSES]
    )
    handled_incidents = repository.fetch_incidents_with_statuses(
        database_session, [status.value for status in HANDLED_INCIDENT_STATUSES]
    )
    rules_by_criticality = incident_response_settings_service.fetch_response_deadline_rules_by_criticality(
        database_session
    )
    current_time = datetime.now(UTC)

    open_incidents_per_criticality = Counter(CriticalityLevel(incident.criticite_actuelle) for incident in open_incidents)
    overdue_open_incident_count = 0
    for incident in open_incidents:
        processing_deadline = compute_processing_deadline(
            incident.created_at, incident.criticite_actuelle, rules_by_criticality
        )
        if processing_deadline is not None and current_time > processing_deadline:
            overdue_open_incident_count += 1

    handling_durations_in_minutes = [
        (
            interpret_stored_datetime_as_utc(incident.traite_le) - interpret_stored_datetime_as_utc(incident.created_at)
        ).total_seconds()
        / 60
        for incident in handled_incidents
        if incident.traite_le is not None
    ]
    handled_incidents_per_day = Counter(
        interpret_stored_datetime_as_utc(incident.traite_le).date()
        for incident in handled_incidents
        if incident.traite_le is not None
    )

    return IncidentStatisticsRead(
        nombre_incidents=repository.count_all_incidents(database_session),
        nombre_incidents_ouverts=len(open_incidents),
        nombre_incidents_traites=len(handled_incidents),
        nombre_incidents_ouverts_delai_depasse=overdue_open_incident_count,
        temps_moyen_traitement_minutes=(
            round(sum(handling_durations_in_minutes) / len(handling_durations_in_minutes), 1)
            if handling_durations_in_minutes
            else None
        ),
        incidents_ouverts_par_criticite={level: open_incidents_per_criticality.get(level, 0) for level in CriticalityLevel},
        incidents_traites_par_jour={
            first_day + timedelta(days=offset): handled_incidents_per_day.get(first_day + timedelta(days=offset), 0)
            for offset in range((last_day - first_day).days + 1)
        },
    )
