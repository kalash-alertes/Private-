"""Tables `incidents` (suivi métier d'un incident issu d'un log) et `etapes_realisees_incident` (avancement du playbook)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.criticality import CriticalityLevel, build_allowed_values_sql_list
from backend.core.database import DatabaseModelBase, TimestampWithTimezoneColumnType


class IncidentStatus(StrEnum):
    # Valeurs PROVISOIRES, à confirmer (explain_project.md, section 15). Un changement exige une migration.
    NEW = "nouveau"
    IN_PROGRESS = "en_cours"
    ON_HOLD = "en_attente"
    RESOLVED = "resolu"
    CLOSED = "cloture"


# Un incident est « traité » (onglet Traités) dès qu'il est résolu ou clôturé ; sinon il est « ouvert » (onglet En cours).
HANDLED_INCIDENT_STATUSES = frozenset({IncidentStatus.RESOLVED, IncidentStatus.CLOSED})
OPEN_INCIDENT_STATUSES = frozenset(set(IncidentStatus) - HANDLED_INCIDENT_STATUSES)

INCIDENT_REFERENCE_PREFIX = "INC-"


def format_incident_reference(numero_reference: int) -> str:
    """Référence lisible affichée à l'analyste, ex. `INC-000042`."""
    return f"{INCIDENT_REFERENCE_PREFIX}{numero_reference:06d}"


class Incident(DatabaseModelBase):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(f"statut IN ({build_allowed_values_sql_list(IncidentStatus)})", name="statut_allowed_values"),
        CheckConstraint(
            f"criticite_actuelle IN ({build_allowed_values_sql_list(CriticalityLevel)})",
            name="criticite_actuelle_allowed_values",
        ),
        # Un faux positif doit toujours être justifié.
        CheckConstraint(
            "faux_positif = false OR (justification IS NOT NULL AND justification <> '')",
            name="faux_positif_requires_justification",
        ),
        # closed_at est renseigné si et seulement si l'incident est clôturé.
        CheckConstraint("(statut = 'cloture') = (closed_at IS NOT NULL)", name="closed_at_set_only_when_closed"),
        CheckConstraint("closed_at IS NULL OR closed_at >= created_at", name="closed_at_not_before_created_at"),
        # traite_le est renseigné si et seulement si l'incident est traité (résolu ou clôturé).
        CheckConstraint(
            "(statut IN ('resolu', 'cloture')) = (traite_le IS NOT NULL)", name="traite_le_set_only_when_handled"
        ),
        CheckConstraint("traite_le IS NULL OR traite_le >= created_at", name="traite_le_not_before_created_at"),
        # Non assigné = NULL, jamais une chaîne vide (sinon deux façons d'exprimer la même chose).
        CheckConstraint("assigne_a IS NULL OR assigne_a <> ''", name="assigne_a_not_blank"),
        CheckConstraint("titre <> ''", name="titre_not_blank"),
        CheckConstraint("categorie <> ''", name="categorie_not_blank"),
        CheckConstraint("numero_reference >= 1", name="numero_reference_positive"),
        Index("ix_incidents_statut", "statut"),
        Index("ix_incidents_assigne_a", "assigne_a"),
        Index("ix_incidents_criticite_actuelle", "criticite_actuelle"),
        Index("ix_incidents_categorie", "categorie"),
        Index("ix_incidents_playbook_id", "playbook_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Numéro séquentiel de la référence lisible (INC-000001). UNIQUE : attribué par le repository (max + 1).
    numero_reference: Mapped[int] = mapped_column(Integer, unique=True)
    # UNIQUE : un log donne au plus un incident en V1.
    log_id: Mapped[UUID] = mapped_column(ForeignKey("logs.id", ondelete="RESTRICT"), unique=True)
    titre: Mapped[str] = mapped_column(String(255))
    # Catégorie d'incident (initialisée avec le type du log) : sert à proposer le playbook de cette catégorie.
    categorie: Mapped[str] = mapped_column(String(255))
    statut: Mapped[str] = mapped_column(String(32), default=IncidentStatus.NEW.value)
    # Criticité évaluée par l'équipe ; initialisée avec criticite_source du log à la création de l'incident.
    criticite_actuelle: Mapped[str] = mapped_column(String(32))
    faux_positif: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    justification: Mapped[str | None] = mapped_column(Text)
    # Texte libre pour l'instant : le type dépendra du futur mécanisme d'authentification (pas de table utilisateurs en V1).
    assigne_a: Mapped[str | None] = mapped_column(String(255))
    # Plan de réponse suivi. SET NULL : supprimer un playbook détache les incidents au lieu de bloquer la suppression.
    playbook_id: Mapped[UUID | None] = mapped_column(ForeignKey("playbooks.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TimestampWithTimezoneColumnType, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(TimestampWithTimezoneColumnType)
    # Date à laquelle l'incident est devenu « traité » : sert à dire si le délai de traitement a été respecté.
    traite_le: Mapped[datetime | None] = mapped_column(TimestampWithTimezoneColumnType)
    # Date de l'escalade automatique (délai dépassé) ; NULL = jamais escaladé. Une seule escalade par incident.
    escalade_le: Mapped[datetime | None] = mapped_column(TimestampWithTimezoneColumnType)


class IncidentPlaybookStepCompletion(DatabaseModelBase):
    """Une étape de playbook marquée « réalisée » pour un incident. Absence de ligne = étape non réalisée."""

    __tablename__ = "etapes_realisees_incident"
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "etape_playbook_id", name="uq_etapes_realisees_incident_incident_id_etape_playbook_id"
        ),
        CheckConstraint("realisee_par IS NULL OR realisee_par <> ''", name="realisee_par_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    # CASCADE : une étape retirée du playbook disparaît aussi de l'avancement des incidents.
    etape_playbook_id: Mapped[UUID] = mapped_column(ForeignKey("etapes_playbook.id", ondelete="CASCADE"))
    realisee_le: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    realisee_par: Mapped[str | None] = mapped_column(String(255))
