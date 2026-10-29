"""Traçage des actions sur les incidents dans le journal d'audit (fonctionnalité `audit_journal`, via son service public).

L'événement est ajouté à la transaction en cours : il n'est enregistré que si la modification l'est aussi.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import NewAuditEventData
from backend.features.incidents.models import Incident, format_incident_reference


def record_incident_audit_event(
    database_session: Session,
    incident: Incident,
    event_type: AuditEventType,
    description: str,
    details: dict[str, Any] | None = None,
    acteur: str | None = None,
) -> None:
    """Ajoute un événement « incident » au journal (sans commit). La description est préfixée par la référence."""
    audit_journal_service.record_audit_event(
        database_session,
        NewAuditEventData(
            type_evenement=event_type,
            description=f"{format_incident_reference(incident.numero_reference)} : {description}",
            acteur=acteur,
            type_ressource="incident",
            identifiant_ressource=str(incident.id),
            details=details,
        ),
    )
