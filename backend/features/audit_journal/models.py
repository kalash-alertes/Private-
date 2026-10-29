"""Table `journal_audit` : un événement survenu dans le système (connexion, modification d'incident, de paramètres...).

Le journal est en ajout seul : aucune route ne permet de modifier ou supprimer un événement.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.criticality import build_allowed_values_sql_list
from backend.core.database import DatabaseModelBase, JsonDocumentColumnType, TimestampWithTimezoneColumnType


class AuditEventType(StrEnum):
    # Connexions : prêtes pour la future authentification (aucune connexion n'existe encore dans l'application).
    LOGIN_SUCCEEDED = "connexion_reussie"
    LOGIN_FAILED = "connexion_echouee"
    LOGOUT = "deconnexion"
    INCIDENT_CREATED = "incident_cree"
    INCIDENT_UPDATED = "incident_modifie"
    INCIDENT_ESCALATED = "incident_escalade"
    PLAYBOOK_CREATED = "playbook_cree"
    PLAYBOOK_UPDATED = "playbook_modifie"
    PLAYBOOK_DELETED = "playbook_supprime"
    SETTINGS_UPDATED = "parametres_modifies"


class AuditEvent(DatabaseModelBase):
    __tablename__ = "journal_audit"
    __table_args__ = (
        CheckConstraint(
            f"type_evenement IN ({build_allowed_values_sql_list(AuditEventType)})", name="type_evenement_allowed_values"
        ),
        CheckConstraint("description <> ''", name="description_not_blank"),
        Index("ix_journal_audit_date_evenement", "date_evenement"),
        Index("ix_journal_audit_type_evenement", "type_evenement"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    date_evenement: Mapped[datetime] = mapped_column(TimestampWithTimezoneColumnType, server_default=func.now())
    type_evenement: Mapped[str] = mapped_column(String(64))
    # Texte libre tant qu'il n'y a pas d'authentification ; NULL = action automatique du système (ex. escalade).
    acteur: Mapped[str | None] = mapped_column(String(255))
    # Ressource concernée (ex. `incident` + son id), pour que l'interface puisse ouvrir l'élément lié.
    type_ressource: Mapped[str | None] = mapped_column(String(64))
    identifiant_ressource: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JsonDocumentColumnType)
    adresse_ip: Mapped[str | None] = mapped_column(String(64))
