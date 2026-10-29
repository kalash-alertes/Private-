"""Routes HTTP de la collecte des alertes. Aucune logique métier ici : tout passe par `service.py`."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.settings import get_application_settings
from backend.features.log_collection import service
from backend.features.log_collection.schemas import LogCollectionConfigurationRead, LogCollectionResultRead

log_collection_router = APIRouter(prefix="/collecte", tags=["collecte"])

DatabaseSession = Annotated[Session, Depends(get_database_session)]


@log_collection_router.get("/configuration", response_model=LogCollectionConfigurationRead)
def read_collection_configuration() -> LogCollectionConfigurationRead:
    """Mode (démonstration ou FortiAnalyzer), adresse, ADOM, variables manquantes. Aucun secret."""
    return service.describe_collection_configuration(get_application_settings())


@log_collection_router.post("", response_model=LogCollectionResultRead)
def run_log_collection(database_session: DatabaseSession) -> LogCollectionResultRead:
    """Lance une collecte maintenant ; le bilan indique le statut (une panne de la source donne « echouee »)."""
    return service.collect_critical_logs_from_configured_source(database_session)
