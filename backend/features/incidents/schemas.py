"""Schémas Pydantic de la fonctionnalité `incidents` : requêtes d'action, filtres et sorties API."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field, model_validator

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import StoredUtcDatetime
from backend.features.incidents.models import IncidentStatus, OPEN_INCIDENT_STATUSES, format_incident_reference

MAXIMUM_JUSTIFICATION_LENGTH = 5000

AssigneeIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
JustificationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAXIMUM_JUSTIFICATION_LENGTH)
]
IncidentShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class IncidentListView(StrEnum):
    """Onglets de la liste des incidents."""

    IN_PROGRESS = "en_cours"  # nouveau, en_cours, en_attente
    HANDLED = "traites"  # resolu, cloture


class IncidentCreationRequest(BaseModel):
    """`titre` et `categorie` sont facultatifs : par défaut, ils sont déduits du type du log."""

    model_config = ConfigDict(extra="forbid")

    log_id: UUID
    titre: IncidentShortText | None = None
    categorie: IncidentShortText | None = None


class IncidentStatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statut: IncidentStatus


class IncidentCriticalityChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criticite_actuelle: CriticalityLevel


class IncidentTitleChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titre: IncidentShortText


class IncidentCategoryChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categorie: IncidentShortText


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


class IncidentPlaybookAssignmentRequest(BaseModel):
    """`playbook_id=null` retire le playbook de l'incident."""

    model_config = ConfigDict(extra="forbid")

    playbook_id: UUID | None


class IncidentPlaybookStepCompletionRequest(BaseModel):
    """Marquer une étape du playbook comme réalisée (`true`) ou non réalisée (`false`)."""

    model_config = ConfigDict(extra="forbid")

    realisee: bool
    realisee_par: AssigneeIdentifier | None = None


class IncidentRead(BaseModel):
    """Champs stockés d'un incident, plus la référence lisible et l'état ouvert/traité qui en découlent."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero_reference: int
    log_id: UUID
    titre: str
    categorie: str
    statut: IncidentStatus
    criticite_actuelle: CriticalityLevel
    faux_positif: bool
    justification: str | None
    assigne_a: str | None
    playbook_id: UUID | None
    created_at: StoredUtcDatetime
    updated_at: StoredUtcDatetime
    closed_at: StoredUtcDatetime | None
    traite_le: StoredUtcDatetime | None
    escalade_le: StoredUtcDatetime | None

    @computed_field
    @property
    def reference(self) -> str:
        return format_incident_reference(self.numero_reference)

    @computed_field
    @property
    def est_ouvert(self) -> bool:
        """Vrai tant que l'incident n'est ni résolu ni clôturé (onglet « en cours »)."""
        return self.statut in OPEN_INCIDENT_STATUSES


class IncidentPlanSummaryRead(BaseModel):
    """Colonne « Plan » de la liste : playbook suivi et avancement."""

    playbook_id: UUID
    nom: str
    nombre_etapes: int
    nombre_etapes_realisees: int


class IncidentListItemRead(IncidentRead):
    """Ligne de la liste des incidents : champs stockés + valeurs calculées (délai, alertes, plan).

    `date_limite_traitement` = `created_at` + délai de la criticité actuelle (Paramètres) ; None si aucun délai défini.
    `delai_depasse` : incident ouvert ⇒ date limite passée ; incident traité ⇒ traité après la date limite.
    """

    date_limite_traitement: datetime | None
    delai_depasse: bool | None
    nombre_alertes: int
    plan: IncidentPlanSummaryRead | None


class IncidentAlertRead(BaseModel):
    """Alerte (log FortiAnalyzer) à l'origine de l'incident."""

    log_id: UUID
    identifiant_source: str
    type: str
    criticite_source: CriticalityLevel
    date_evenement: datetime


class IncidentDetailRead(IncidentListItemRead):
    """Détail d'un incident, avec la criticité source du log pour comparer avec la criticité réévaluée."""

    criticite_source: CriticalityLevel
    alertes: list[IncidentAlertRead]


class IncidentPlaybookStepProgressRead(BaseModel):
    id: UUID
    ordre: int
    titre: str
    description: str | None
    est_realisee: bool
    realisee_le: StoredUtcDatetime | None
    realisee_par: str | None


class IncidentPlaybookProgressRead(BaseModel):
    playbook_id: UUID
    nom: str
    description: str | None
    categorie: str | None
    source: str
    nombre_etapes: int
    nombre_etapes_realisees: int
    etapes: list[IncidentPlaybookStepProgressRead]


class IncidentPlaybookRead(BaseModel):
    """Ce qu'affiche un clic sur un incident : son playbook et l'avancement de chaque étape (`playbook=null` : aucun)."""

    incident_id: UUID
    reference: str
    playbook: IncidentPlaybookProgressRead | None


class AutomaticEscalationResultRead(BaseModel):
    nombre_incidents_escalades: int
    incidents_escalades: list[UUID]


class IncidentStatisticsRead(BaseModel):
    """Indicateurs d'incidents pour le tableau de bord."""

    nombre_incidents: int
    nombre_incidents_ouverts: int
    nombre_incidents_traites: int
    nombre_incidents_ouverts_delai_depasse: int
    # Temps moyen entre création et traitement (résolu/clôturé) ; None s'il n'y a encore aucun incident traité.
    temps_moyen_traitement_minutes: float | None
    incidents_ouverts_par_criticite: dict[CriticalityLevel, int]
    incidents_traites_par_jour: dict[date, int]


class IncidentListFilters(BaseModel):
    vue: IncidentListView | None = None
    recherche: str | None = None
    statut: IncidentStatus | None = None
    criticite_actuelle: CriticalityLevel | None = None
    faux_positif: bool | None = None
    assigne_a: str | None = None
    categorie: str | None = None
    playbook_id: UUID | None = None
    log_id: UUID | None = None
