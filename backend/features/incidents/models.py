"""Table `incidents` : suivi métier d'un incident issu d'un log."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, false, func
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
        # Non assigné = NULL, jamais une chaîne vide (sinon deux façons d'exprimer la même chose).
        CheckConstraint("assigne_a IS NULL OR assigne_a <> ''", name="assigne_a_not_blank"),
        Index("ix_incidents_statut", "statut"),
        Index("ix_incidents_assigne_a", "assigne_a"),
        Index("ix_incidents_criticite_actuelle", "criticite_actuelle"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # UNIQUE : un log donne au plus un incident en V1.
    log_id: Mapped[UUID] = mapped_column(ForeignKey("logs.id", ondelete="RESTRICT"), unique=True)
    statut: Mapped[str] = mapped_column(String(32), default=IncidentStatus.NEW.value)
    # Criticité évaluée par l'équipe ; initialisée avec criticite_source du log à la création de l'incident.
    criticite_actuelle: Mapped[str] = mapped_column(String(32))
    faux_positif: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    justification: Mapped[str | None] = mapped_column(Text)
    # Texte libre pour l'instant : le type dépendra du futur mécanisme d'authentification (pas de table utilisateurs en V1).
    assigne_a: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TimestampWithTimezoneColumnType, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(TimestampWithTimezoneColumnType)
