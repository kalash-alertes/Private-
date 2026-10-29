"""Route HTTP du tableau de bord. Aucune logique métier ici : tout passe par `service.py`."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.features.dashboard import service
from backend.features.dashboard.schemas import DashboardRead

dashboard_router = APIRouter(prefix="/tableau-de-bord", tags=["tableau_de_bord"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


@dashboard_router.get("", response_model=DashboardRead)
def read_dashboard(
    database_session: DatabaseSession,
    nombre_jours: Annotated[int, Query(ge=1, le=90, description="Jours couverts par le graphique d'activité")] = 7,
) -> DashboardRead:
    """Indicateurs (incidents ouverts, alertes à traiter, temps moyen...) et activité quotidienne."""
    return service.build_dashboard(database_session, nombre_jours)
