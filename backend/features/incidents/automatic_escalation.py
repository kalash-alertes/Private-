"""Escalade automatique des incidents dont le délai de traitement est dépassé.

Règle (Paramètres > Réponse aux incidents) : un incident OUVERT, jamais escaladé, dont la date limite est passée et
dont la criticité actuelle a l'escalade automatique activée est escaladé :
- `escalade_le` est renseigné (une seule escalade par incident, même s'il reste en retard) ;
- s'il y a une cible d'escalade, l'incident lui est réattribué (`assigne_a`) ;
- l'escalade est tracée dans le journal d'audit (acteur NULL = système).
L'escalade ne modifie ni le statut ni la criticité, et n'agit jamais sur l'infrastructure.

Déclenchement : `POST /incidents/escalade-automatique` (manuel) et/ou la boucle périodique ci-dessous, activée par
`AUTOMATIC_ESCALATION_INTERVAL_SECONDS` > 0 (désactivée par défaut, donc dans les tests).
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from backend.core.criticality import CriticalityLevel
from backend.features.audit_journal.models import AuditEventType
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incidents import repository
from backend.features.incidents.incident_audit_trail import record_incident_audit_event
from backend.features.incidents.incident_views import compute_processing_deadline
from backend.features.incidents.models import OPEN_INCIDENT_STATUSES
from backend.features.incidents.schemas import AutomaticEscalationResultRead

automatic_escalation_logger = logging.getLogger(__name__)


def escalate_overdue_incidents(database_session: Session) -> AutomaticEscalationResultRead:
    """Escalade tous les incidents en retard éligibles, en une transaction. Retourne les incidents escaladés."""
    rules_by_criticality = incident_response_settings_service.fetch_response_deadline_rules_by_criticality(
        database_session
    )
    current_time = datetime.now(UTC)
    escalated_incident_ids = []
    for incident in repository.fetch_open_incidents_not_yet_escalated_for_update(
        database_session, [status.value for status in OPEN_INCIDENT_STATUSES]
    ):
        rule = rules_by_criticality.get(CriticalityLevel(incident.criticite_actuelle))
        if rule is None or not rule.escalade_automatique_activee:
            continue
        processing_deadline = compute_processing_deadline(
            incident.created_at, incident.criticite_actuelle, rules_by_criticality
        )
        if processing_deadline is None or current_time <= processing_deadline:
            continue

        incident.escalade_le = func.now()
        previous_assignee = incident.assigne_a
        if rule.escalader_vers is not None:
            incident.assigne_a = rule.escalader_vers
        record_incident_audit_event(
            database_session,
            incident,
            AuditEventType.INCIDENT_ESCALATED,
            f"délai de traitement dépassé (date limite {processing_deadline.isoformat()}), escalade automatique.",
            {
                "date_limite_traitement": processing_deadline.isoformat(),
                "assigne_a_avant": previous_assignee,
                "assigne_a_apres": incident.assigne_a,
            },
        )
        escalated_incident_ids.append(incident.id)
    database_session.commit()
    return AutomaticEscalationResultRead(
        nombre_incidents_escalades=len(escalated_incident_ids), incidents_escalades=escalated_incident_ids
    )


async def run_automatic_escalation_periodically(
    database_session_factory: sessionmaker[Session], interval_seconds: float
) -> None:
    """Boucle de fond : lance l'escalade toutes les `interval_seconds` secondes, jusqu'à annulation de la tâche.

    Une erreur est journalisée puis la boucle continue : une panne passagère de la base ne doit pas arrêter
    définitivement l'escalade.
    """

    def escalate_with_new_session() -> AutomaticEscalationResultRead:
        with database_session_factory() as database_session:
            return escalate_overdue_incidents(database_session)

    while True:
        try:
            escalation_result = await run_in_threadpool(escalate_with_new_session)
            if escalation_result.nombre_incidents_escalades:
                automatic_escalation_logger.info(
                    "Escalade automatique : %s incident(s) escaladé(s).", escalation_result.nombre_incidents_escalades
                )
        except Exception:
            automatic_escalation_logger.exception("Échec de l'escalade automatique ; nouvel essai au prochain tour.")
        await asyncio.sleep(interval_seconds)
