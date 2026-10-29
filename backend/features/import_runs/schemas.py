"""Schémas Pydantic de la fonctionnalité `import_runs` : sorties API et données d'entrée des services internes."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.utc_datetime_types import StoredUtcDatetime
from backend.features.import_runs.models import ImportRunStatus


class FinishedImportRunStatus(StrEnum):
    """Statuts possibles à la fin d'une exécution (tous sauf `en_cours`)."""

    SUCCEEDED = ImportRunStatus.SUCCEEDED.value
    PARTIALLY_SUCCEEDED = ImportRunStatus.PARTIALLY_SUCCEEDED.value
    FAILED = ImportRunStatus.FAILED.value


class ImportRunRead(BaseModel):
    """Une exécution d'import telle qu'exposée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    debut: StoredUtcDatetime
    fin: StoredUtcDatetime | None
    statut: ImportRunStatus
    nb_logs_recus: int
    nb_logs_inseres: int
    nb_logs_ignores: int
    erreur: str | None
    curseur_synchronisation: str | None
    created_at: StoredUtcDatetime


class ImportRunListFilters(BaseModel):
    statut: ImportRunStatus | None = None


class ImportRunFinishedOutcome(BaseModel):
    """Résultat d'une exécution, fourni par le collecteur pour la terminer.

    Définitions des compteurs (cf. docs/technical/import_runs.md) :
    - `nb_logs_recus` : logs renvoyés par la source pendant l'exécution ;
    - `nb_logs_inseres` : logs nouveaux réellement enregistrés (`was_inserted=True` côté `source_logs`) ;
    - `nb_logs_ignores` : logs déjà connus (doublons), donc non recréés ;
    - la différence `recus - inseres - ignores` = logs rejetés (invalides ou non enregistrés).
    """

    model_config = ConfigDict(extra="forbid")

    statut: FinishedImportRunStatus
    nb_logs_recus: int = Field(ge=0)
    nb_logs_inseres: int = Field(ge=0)
    nb_logs_ignores: int = Field(ge=0)
    erreur: str | None = None
    curseur_synchronisation: str | None = None

    @model_validator(mode="after")
    def check_counters_and_error_are_consistent_with_status(self) -> "ImportRunFinishedOutcome":
        processed_logs_count = self.nb_logs_inseres + self.nb_logs_ignores
        if processed_logs_count > self.nb_logs_recus:
            raise ValueError("nb_logs_inseres + nb_logs_ignores ne peut pas dépasser nb_logs_recus")
        has_error_message = bool(self.erreur and self.erreur.strip())
        if self.statut == FinishedImportRunStatus.SUCCEEDED:
            # Une réussite signifie que chaque log reçu a été enregistré ou reconnu comme doublon.
            if has_error_message:
                raise ValueError("une exécution réussie ne porte pas de message d'erreur")
            if processed_logs_count != self.nb_logs_recus:
                raise ValueError("une exécution avec des logs rejetés doit être terminée en 'partielle' ou 'echouee'")
        elif not has_error_message:
            raise ValueError("une exécution partielle ou échouée doit fournir un message d'erreur exploitable")
        return self
