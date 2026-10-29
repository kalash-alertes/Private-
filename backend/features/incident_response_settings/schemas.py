"""Schémas Pydantic de la fonctionnalité `incident_response_settings`."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import StoredUtcDatetime

# Borne haute de bon sens (1 an) : évite qu'une faute de frappe repousse une date limite à l'infini.
MAXIMUM_RESPONSE_DELAY_MINUTES = 525_600

EscalationTargetIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ResponseDeadlineRuleUpdateRequest(BaseModel):
    """Nouvelle règle complète pour une criticité. `escalader_vers=null` : escalade sans changement de responsable."""

    model_config = ConfigDict(extra="forbid")

    delai_traitement_minutes: int = Field(ge=1, le=MAXIMUM_RESPONSE_DELAY_MINUTES)
    escalade_automatique_activee: bool
    escalader_vers: EscalationTargetIdentifier | None = None


class ResponseDeadlineRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    criticite: CriticalityLevel
    delai_traitement_minutes: int
    escalade_automatique_activee: bool
    escalader_vers: str | None
    updated_at: StoredUtcDatetime
