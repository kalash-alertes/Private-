"""Calcul du tableau de bord, à partir des services publics de `source_logs` et `incidents`.

Aucune requête SQL ici : la fonctionnalité n'a pas de table et ne lit pas celles des autres.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.features.dashboard.schemas import DailyActivityRead, DashboardRead
from backend.features.incidents import incident_statistics
from backend.features.source_logs import service as source_logs_service

DEFAULT_ACTIVITY_DAY_COUNT = 7


def build_dashboard(database_session: Session, activity_day_count: int = DEFAULT_ACTIVITY_DAY_COUNT) -> DashboardRead:
    """Retourne les indicateurs et l'activité des `activity_day_count` derniers jours (UTC, aujourd'hui compris)."""
    last_day = datetime.now(UTC).date()
    first_day = last_day - timedelta(days=activity_day_count - 1)
    incident_statistics_result = incident_statistics.compute_incident_statistics(database_session, first_day, last_day)
    logs_per_day = source_logs_service.count_source_logs_per_event_day(database_session, first_day, last_day)
    total_log_count = source_logs_service.count_all_source_logs(database_session)

    return DashboardRead(
        nombre_incidents_ouverts=incident_statistics_result.nombre_incidents_ouverts,
        nombre_incidents_traites=incident_statistics_result.nombre_incidents_traites,
        nombre_incidents_ouverts_delai_depasse=incident_statistics_result.nombre_incidents_ouverts_delai_depasse,
        nombre_alertes_a_traiter=max(total_log_count - incident_statistics_result.nombre_incidents, 0),
        nombre_alertes=total_log_count,
        temps_moyen_traitement_minutes=incident_statistics_result.temps_moyen_traitement_minutes,
        incidents_ouverts_par_criticite=incident_statistics_result.incidents_ouverts_par_criticite,
        activite=[
            DailyActivityRead(
                jour=day,
                alertes_detectees=logs_per_day[day],
                incidents_traites=incident_statistics_result.incidents_traites_par_jour[day],
            )
            for day in sorted(logs_per_day)
        ],
    )
