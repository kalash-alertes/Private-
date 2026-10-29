"""Table `delais_reponse_incidents` : une règle par niveau de criticité (délai de traitement + escalade automatique).

Les cinq lignes (une par criticité) sont créées par la migration 0003 avec des valeurs PAR DÉFAUT à ajuster par
l'équipe ; l'API ne permet que de les modifier, jamais d'en ajouter ou d'en supprimer.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.criticality import CriticalityLevel, build_allowed_values_sql_list
from backend.core.database import DatabaseModelBase, TimestampWithTimezoneColumnType


class IncidentResponseDeadlineRule(DatabaseModelBase):
    __tablename__ = "delais_reponse_incidents"
    __table_args__ = (
        CheckConstraint(
            f"criticite IN ({build_allowed_values_sql_list(CriticalityLevel)})", name="criticite_allowed_values"
        ),
        CheckConstraint("delai_traitement_minutes > 0", name="delai_traitement_minutes_positive"),
        CheckConstraint("escalader_vers IS NULL OR escalader_vers <> ''", name="escalader_vers_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # UNIQUE : une seule règle par criticité.
    criticite: Mapped[str] = mapped_column(String(32), unique=True)
    # Délai entre la création de l'incident et sa date limite de traitement.
    delai_traitement_minutes: Mapped[int] = mapped_column(Integer)
    escalade_automatique_activee: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Responsable à qui l'incident est réattribué à l'escalade (texte libre, comme `incidents.assigne_a`).
    # NULL : l'incident est seulement marqué « escaladé », sans changer de responsable.
    escalader_vers: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        TimestampWithTimezoneColumnType, server_default=func.now(), onupdate=func.now()
    )
