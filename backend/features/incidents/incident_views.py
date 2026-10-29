"""Construction des vues d'incidents exposées à l'interface (liste et détail) : valeurs calculées comprises.

Valeurs calculées (non stockées, toujours à jour avec les Paramètres) :
- date limite de traitement = `created_at` + délai de la criticité ACTUELLE (Paramètres > Réponse aux incidents) ;
- délai dépassé : incident ouvert ⇒ maintenant > date limite ; incident traité ⇒ `traite_le` > date limite ;
- plan : playbook suivi + nombre d'étapes réalisées (seules les étapes du playbook ACTUEL comptent) ;
- alertes : le log à l'origine de l'incident (un seul en V1, d'où une liste prête pour plusieurs alertes plus tard).

Les données des autres fonctionnalités (logs, playbooks, délais) sont chargées en une requête par page, pas par ligne.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.utc_datetime_types import interpret_stored_datetime_as_utc
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incident_response_settings.schemas import ResponseDeadlineRuleRead
from backend.features.incidents import repository
from backend.features.incidents.models import Incident
from backend.features.incidents.schemas import (
    IncidentAlertRead,
    IncidentDetailRead,
    IncidentListItemRead,
    IncidentPlanSummaryRead,
    IncidentRead,
)
from backend.features.playbooks import service as playbooks_service
from backend.features.playbooks.schemas import PlaybookDetailRead
from backend.features.source_logs import service as source_logs_service


def compute_processing_deadline(
    created_at: datetime, criticite: str, rules_by_criticality: dict[CriticalityLevel, ResponseDeadlineRuleRead]
) -> datetime | None:
    """Retourne la date limite de traitement (UTC), ou None si aucun délai n'est défini pour cette criticité."""
    rule = rules_by_criticality.get(CriticalityLevel(criticite))
    if rule is None:
        return None
    return interpret_stored_datetime_as_utc(created_at) + timedelta(minutes=rule.delai_traitement_minutes)


def is_processing_deadline_exceeded(
    traite_le: datetime | None, processing_deadline: datetime | None, current_time: datetime
) -> bool | None:
    """Vrai si le délai est (ou a été) dépassé ; None si l'incident n'a pas de date limite."""
    if processing_deadline is None:
        return None
    reference_time = interpret_stored_datetime_as_utc(traite_le) if traite_le is not None else current_time
    return reference_time > processing_deadline


def build_incident_list_items(database_session: Session, incidents: list[Incident]) -> list[IncidentListItemRead]:
    """Construit les lignes de liste d'une page d'incidents (requêtes groupées pour toute la page)."""
    rules_by_criticality = incident_response_settings_service.fetch_response_deadline_rules_by_criticality(
        database_session
    )
    playbooks_by_id = playbooks_service.fetch_playbook_details_by_ids(
        database_session, [incident.playbook_id for incident in incidents if incident.playbook_id is not None]
    )
    completed_step_ids_by_incident_id = repository.fetch_completed_step_ids_by_incident_id(
        database_session, [incident.id for incident in incidents]
    )
    current_time = datetime.now(UTC)
    return [
        _build_incident_list_item(
            incident,
            rules_by_criticality,
            playbooks_by_id.get(incident.playbook_id) if incident.playbook_id is not None else None,
            completed_step_ids_by_incident_id[incident.id],
            current_time,
        )
        for incident in incidents
    ]


def build_incident_detail(database_session: Session, incident: Incident) -> IncidentDetailRead:
    """Construit le détail d'un incident : ligne de liste + criticité source et alertes d'origine."""
    incident_list_item = build_incident_list_items(database_session, [incident])[0]
    source_log = source_logs_service.fetch_source_log_metadata(database_session, incident.log_id)
    return IncidentDetailRead(
        **incident_list_item.model_dump(exclude={"reference", "est_ouvert"}),
        criticite_source=source_log.criticite_source,
        alertes=[
            IncidentAlertRead(
                log_id=source_log.id,
                identifiant_source=source_log.identifiant_source,
                type=source_log.type,
                criticite_source=source_log.criticite_source,
                date_evenement=source_log.date_evenement,
            )
        ],
    )


def _build_incident_list_item(
    incident: Incident,
    rules_by_criticality: dict[CriticalityLevel, ResponseDeadlineRuleRead],
    playbook: PlaybookDetailRead | None,
    completed_step_ids: set[UUID],
    current_time: datetime,
) -> IncidentListItemRead:
    processing_deadline = compute_processing_deadline(incident.created_at, incident.criticite_actuelle, rules_by_criticality)
    plan = None
    if playbook is not None:
        playbook_step_ids = {step.id for step in playbook.etapes}
        plan = IncidentPlanSummaryRead(
            playbook_id=playbook.id,
            nom=playbook.nom,
            nombre_etapes=len(playbook_step_ids),
            nombre_etapes_realisees=len(playbook_step_ids & completed_step_ids),
        )
    return IncidentListItemRead(
        **IncidentRead.model_validate(incident).model_dump(exclude={"reference", "est_ouvert"}),
        date_limite_traitement=processing_deadline,
        delai_depasse=is_processing_deadline_exceeded(incident.traite_le, processing_deadline, current_time),
        # Un log = un incident en V1 : toujours une alerte. Le champ reste pour l'interface si cela évolue.
        nombre_alertes=1,
        plan=plan,
    )
