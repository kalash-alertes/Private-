"""Table `logs` : logs critiques connus de l'application (métadonnées + référence OpenSearch)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.criticality import CriticalityLevel, build_allowed_values_sql_list
from backend.core.database import DatabaseModelBase, JsonDocumentColumnType, TimestampWithTimezoneColumnType


class SourceLog(DatabaseModelBase):
    __tablename__ = "logs"
    __table_args__ = (
        CheckConstraint(
            f"criticite_source IN ({build_allowed_values_sql_list(CriticalityLevel)})",
            name="criticite_source_allowed_values",
        ),
        # Une chaîne vide ne peut pas servir de clé de déduplication.
        CheckConstraint("identifiant_source <> ''", name="identifiant_source_not_blank"),
        Index("ix_logs_date_evenement", "date_evenement"),
        Index("ix_logs_criticite_source", "criticite_source"),
        Index("ix_logs_execution_import_id", "execution_import_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Clé de déduplication : UNIQUE. Si FortiAnalyzer ne fournit pas d'identifiant stable,
    # le collecteur doit en calculer un de façon déterministe (à documenter dans la doc technique du collecteur).
    identifiant_source: Mapped[str] = mapped_column(String(255), unique=True)
    date_evenement: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType)
    type: Mapped[str] = mapped_column(String(255))
    # Criticité d'origine FortiAnalyzer : ne jamais la modifier (la réévaluation vit dans `incidents`).
    criticite_source: Mapped[str] = mapped_column(String(32))
    donnees_brutes: Mapped[dict | None] = mapped_column(JsonDocumentColumnType)
    reference_opensearch: Mapped[str | None] = mapped_column(String(255))
    arrivee_db: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    # Exécution qui a enregistré ce log pour la première fois.
    execution_import_id: Mapped[UUID] = mapped_column(ForeignKey("executions_import.id", ondelete="RESTRICT"))
