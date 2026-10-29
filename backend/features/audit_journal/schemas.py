"""Schémas Pydantic de la fonctionnalité `audit_journal` : événement à enregistrer, filtres et sorties API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from backend.core.utc_datetime_types import AwareUtcDatetimeInput, StoredUtcDatetime
from backend.features.audit_journal.models import AuditEventType


class NewAuditEventData(BaseModel):
    """Événement à enregistrer, fourni par les autres fonctionnalités (jamais par une route HTTP)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type_evenement: AuditEventType
    description: str
    acteur: str | None = None
    type_ressource: str | None = None
    identifiant_ressource: str | None = None
    details: dict[str, Any] | None = None
    adresse_ip: str | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date_evenement: StoredUtcDatetime
    type_evenement: AuditEventType
    acteur: str | None
    type_ressource: str | None
    identifiant_ressource: str | None
    description: str
    details: dict[str, Any] | None
    adresse_ip: str | None


class AuditEventListFilters(BaseModel):
    """Filtres du journal. Les bornes de date sont incluses."""

    type_evenement: AuditEventType | None = None
    acteur: str | None = None
    type_ressource: str | None = None
    identifiant_ressource: str | None = None
    date_evenement_min: AwareUtcDatetimeInput | None = None
    date_evenement_max: AwareUtcDatetimeInput | None = None

    @model_validator(mode="after")
    def check_date_range_is_ordered(self) -> "AuditEventListFilters":
        if self.date_evenement_min and self.date_evenement_max and self.date_evenement_min > self.date_evenement_max:
            raise ValueError("date_evenement_min doit être antérieure ou égale à date_evenement_max")
        return self
