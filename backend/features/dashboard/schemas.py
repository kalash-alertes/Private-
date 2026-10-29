"""Schémas Pydantic de la fonctionnalité `dashboard`."""

from datetime import date

from pydantic import BaseModel

from backend.core.criticality import CriticalityLevel


class DailyActivityRead(BaseModel):
    """Un point du graphique « Activité des alertes »."""

    jour: date
    alertes_detectees: int
    incidents_traites: int


class DashboardRead(BaseModel):
    nombre_incidents_ouverts: int
    nombre_incidents_traites: int
    nombre_incidents_ouverts_delai_depasse: int
    # Alertes (logs) sans incident : un log donne au plus un incident en V1, d'où logs - incidents.
    nombre_alertes_a_traiter: int
    nombre_alertes: int
    temps_moyen_traitement_minutes: float | None
    incidents_ouverts_par_criticite: dict[CriticalityLevel, int]
    activite: list[DailyActivityRead]
