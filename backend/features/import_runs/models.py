"""Table `executions_import` : une ligne par tentative de collecte depuis FortiAnalyzer."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.criticality import build_allowed_values_sql_list
from backend.core.database import DatabaseModelBase, TimestampWithTimezoneColumnType


class ImportRunStatus(StrEnum):
    IN_PROGRESS = "en_cours"
    SUCCEEDED = "reussie"
    PARTIALLY_SUCCEEDED = "partielle"
    FAILED = "echouee"


class ImportRun(DatabaseModelBase):
    __tablename__ = "executions_import"
    __table_args__ = (
        CheckConstraint(f"statut IN ({build_allowed_values_sql_list(ImportRunStatus)})", name="statut_allowed_values"),
        # Une exécution n'a une date de fin que si elle n'est plus en cours.
        CheckConstraint("(statut = 'en_cours') = (fin IS NULL)", name="fin_set_only_when_finished"),
        CheckConstraint(
            "nb_logs_recus >= 0 AND nb_logs_inseres >= 0 AND nb_logs_ignores >= 0",
            name="log_counters_not_negative",
        ),
        # Un log reçu est soit inséré, soit ignoré (doublon), soit rejeté : la différence recus - inseres - ignores
        # correspond aux logs rejetés (invalides). Cf. migration 0002 et docs/technical/import_runs.md.
        CheckConstraint(
            "nb_logs_inseres + nb_logs_ignores <= nb_logs_recus", name="processed_logs_not_above_received_logs"
        ),
        # Un échec ou une réussite partielle doit toujours être expliqué ; une réussite ne porte pas d'erreur.
        CheckConstraint(
            "statut NOT IN ('partielle', 'echouee') OR (erreur IS NOT NULL AND erreur <> '')",
            name="erreur_required_when_partial_or_failed",
        ),
        CheckConstraint("statut <> 'reussie' OR erreur IS NULL", name="erreur_absent_when_succeeded"),
        CheckConstraint("fin IS NULL OR fin >= debut", name="fin_not_before_debut"),
        Index("ix_executions_import_debut", "debut"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    debut: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    fin: Mapped[datetime | None] = mapped_column(TimestampWithTimezoneColumnType)
    statut: Mapped[str] = mapped_column(default=ImportRunStatus.IN_PROGRESS.value)
    nb_logs_recus: Mapped[int] = mapped_column(default=0)
    nb_logs_inseres: Mapped[int] = mapped_column(default=0)
    # Logs déjà connus (doublons) : voir la règle de déduplication dans la doc technique.
    nb_logs_ignores: Mapped[int] = mapped_column(default=0)
    erreur: Mapped[str | None] = mapped_column(Text)
    # Point de reprise : fin de la période de la collecte (ISO 8601, UTC), écrit par log_collection.
    curseur_synchronisation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
