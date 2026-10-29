"""Schémas Pydantic de la fonctionnalité `playbooks`."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from backend.core.utc_datetime_types import StoredUtcDatetime

MAXIMUM_STEPS_PER_PLAYBOOK = 100
MAXIMUM_LONG_TEXT_LENGTH = 10_000

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAXIMUM_LONG_TEXT_LENGTH)]


class PlaybookStepWriteRequest(BaseModel):
    """Une étape à enregistrer. `id` d'une étape existante : elle est conservée (avec son suivi dans les incidents) ;
    sans `id` : nouvelle étape. L'ordre est celui de la liste."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    titre: ShortText
    description: LongText | None = None


class PlaybookWriteRequest(BaseModel):
    """Playbook complet (création ou remplacement). Une étape absente de la liste est supprimée."""

    model_config = ConfigDict(extra="forbid")

    nom: ShortText
    description: LongText | None = None
    categorie: ShortText | None = None
    source: LongText = Field(description="Référence vérifiable : documentation officielle, procédure interne validée")
    etapes: list[PlaybookStepWriteRequest] = Field(min_length=1, max_length=MAXIMUM_STEPS_PER_PLAYBOOK)

    @model_validator(mode="after")
    def check_step_identifiers_are_unique(self) -> "PlaybookWriteRequest":
        step_identifiers = [step.id for step in self.etapes if step.id is not None]
        if len(step_identifiers) != len(set(step_identifiers)):
            raise ValueError("une même étape (id) ne peut apparaître qu'une fois")
        return self


class PlaybookStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordre: int
    titre: str
    description: str | None


class PlaybookSummaryRead(BaseModel):
    """Vue courte pour les listes (sans le détail des étapes)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom: str
    categorie: str | None
    nombre_etapes: int
    updated_at: StoredUtcDatetime


class PlaybookDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nom: str
    description: str | None
    categorie: str | None
    source: str
    etapes: list[PlaybookStepRead]
    created_at: StoredUtcDatetime
    updated_at: StoredUtcDatetime


class PlaybookListFilters(BaseModel):
    categorie: str | None = None
