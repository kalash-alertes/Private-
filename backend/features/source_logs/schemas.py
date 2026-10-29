"""Schémas Pydantic de la fonctionnalité `source_logs` : sorties API, filtres et données d'insertion internes."""

from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import AwareUtcDatetimeInput, StoredUtcDatetime

NonBlankBoundedText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class NewSourceLogData(BaseModel):
    """Log normalisé à enregistrer, fourni par le collecteur (jamais par une route HTTP publique).

    `date_evenement` doit porter un fuseau horaire : une date sans fuseau est ambiguë et serait mal ordonnée.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifiant_source: NonBlankBoundedText
    date_evenement: AwareUtcDatetimeInput
    type: NonBlankBoundedText
    criticite_source: CriticalityLevel
    donnees_brutes: dict[str, Any] | None = None
    reference_opensearch: NonBlankBoundedText | None = None
    execution_import_id: UUID


class SourceLogStorageResult(BaseModel):
    """Résultat d'une tentative d'enregistrement. `was_inserted=False` : le log existait déjà (doublon ignoré)."""

    source_log_id: UUID
    was_inserted: bool


class SourceLogMetadataRead(BaseModel):
    """Métadonnées d'un log (sans `donnees_brutes`), pour les listes et les autres fonctionnalités."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identifiant_source: str
    date_evenement: StoredUtcDatetime
    type: str
    criticite_source: CriticalityLevel
    reference_opensearch: str | None
    arrivee_db: StoredUtcDatetime
    execution_import_id: UUID


class SourceLogDetailRead(SourceLogMetadataRead):
    """Détail d'un log, avec la copie brute éventuelle (stratégie de stockage encore à décider)."""

    donnees_brutes: dict[str, Any] | None


class SourceLogListFilters(BaseModel):
    """Filtres de la liste des logs. Les bornes de date sont incluses."""

    criticite_source: CriticalityLevel | None = None
    type: str | None = None
    execution_import_id: UUID | None = None
    date_evenement_min: AwareUtcDatetimeInput | None = None
    date_evenement_max: AwareUtcDatetimeInput | None = None

    @model_validator(mode="after")
    def check_date_range_is_ordered(self) -> "SourceLogListFilters":
        if self.date_evenement_min and self.date_evenement_max and self.date_evenement_min > self.date_evenement_max:
            raise ValueError("date_evenement_min doit être antérieure ou égale à date_evenement_max")
        return self
