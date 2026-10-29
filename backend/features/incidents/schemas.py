"""Schémas Pydantic de la fonctionnalité `incidents` : requêtes d'action, filtres et sorties API."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import StoredUtcDatetime
from backend.features.incidents.models import IncidentStatus

MAXIMUM_JUSTIFICATION_LENGTH = 5000

AssigneeIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
JustificationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAXIMUM_JUSTIFICATION_LENGTH)
]


class IncidentCreationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_id: UUID


class IncidentStatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statut: IncidentStatus


class IncidentCriticalityChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criticite_actuelle: CriticalityLevel


class IncidentFalsePositiveQualificationRequest(BaseModel):
    """Qualifier (`faux_positif=true`, justification obligatoire) ou retirer la qualification (`false`).

    Au retrait, la justification est facultative : si elle est absente, l'ancienne est conservée pour garder
    une trace de la décision précédente (pas de table d'historique en V1).
    """

    model_config = ConfigDict(extra="forbid")

    faux_positif: bool
    justification: JustificationText | None = None

    @model_validator(mode="after")
    def check_false_positive_is_justified(self) -> "IncidentFalsePositiveQualificationRequest":
        if self.faux_positif and self.justification is None:
            raise ValueError("une justification non vide est obligatoire pour déclarer un faux positif")
        return self


class IncidentAssignmentRequest(BaseModel):
    """`assigne_a=null` retire l'attribution. Identifiant en texte libre (provisoire, en attente de l'authentification)."""

    model_config = ConfigDict(extra="forbid")

    assigne_a: AssigneeIdentifier | None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    log_id: UUID
    statut: IncidentStatus
    criticite_actuelle: CriticalityLevel
    faux_positif: bool
    justification: str | None
    assigne_a: str | None
    created_at: StoredUtcDatetime
    updated_at: StoredUtcDatetime
    closed_at: StoredUtcDatetime | None


class IncidentDetailRead(IncidentRead):
    """Détail d'un incident, avec la criticité source du log pour comparer avec la criticité réévaluée."""

    criticite_source: CriticalityLevel


class IncidentListFilters(BaseModel):
    statut: IncidentStatus | None = None
    criticite_actuelle: CriticalityLevel | None = None
    faux_positif: bool | None = None
    assigne_a: str | None = None
    log_id: UUID | None = None
