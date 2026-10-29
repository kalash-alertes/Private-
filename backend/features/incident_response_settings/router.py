"""Routes HTTP des paramètres de réponse aux incidents. Aucune logique métier ici : tout passe par `service.py`."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.features.incident_response_settings import service
from backend.features.incident_response_settings.schemas import (
    ResponseDeadlineRuleRead,
    ResponseDeadlineRuleUpdateRequest,
)

incident_response_settings_router = APIRouter(
    prefix="/parametres/reponse-incidents", tags=["parametres_reponse_incidents"]
)

DatabaseSession = Annotated[Session, Depends(get_database_session)]


@incident_response_settings_router.get("/delais", response_model=list[ResponseDeadlineRuleRead])
def list_response_deadline_rules(database_session: DatabaseSession) -> list[ResponseDeadlineRuleRead]:
    """Délais de traitement et escalade automatique, de la criticité la plus grave à la moins grave."""
    return service.list_response_deadline_rules(database_session)


@incident_response_settings_router.put("/delais/{criticite}", response_model=ResponseDeadlineRuleRead)
def update_response_deadline_rule(
    criticite: CriticalityLevel, rule_update: ResponseDeadlineRuleUpdateRequest, database_session: DatabaseSession
) -> ResponseDeadlineRuleRead:
    """Remplace la règle d'une criticité (délai, escalade automatique, cible de l'escalade)."""
    return service.update_response_deadline_rule(database_session, criticite, rule_update)
