"""Playbook d'un incident et avancement de ses étapes (ce que l'interface affiche au clic sur un incident).

Règles :
- l'avancement est propre à chaque incident : une ligne dans `etapes_realisees_incident` par étape réalisée ;
- on ne peut cocher qu'une étape du playbook ACTUEL de l'incident ; cocher deux fois ne change rien ;
- cocher ou décocher une étape met à jour `updated_at` de l'incident (colonne « Mis à jour ») et est tracé dans le
  journal d'audit ;
- PROVISOIRE : un incident clôturé est en lecture seule, comme pour ses autres champs.
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.domain_errors import BusinessRuleViolationError, ResourceNotFoundError
from backend.features.audit_journal.models import AuditEventType
from backend.features.incidents import repository
from backend.features.incidents.incident_audit_trail import record_incident_audit_event
from backend.features.incidents.models import Incident, format_incident_reference
from backend.features.incidents.schemas import (
    IncidentPlaybookProgressRead,
    IncidentPlaybookRead,
    IncidentPlaybookStepCompletionRequest,
    IncidentPlaybookStepProgressRead,
)
from backend.features.incidents.service import fetch_existing_incident, fetch_modifiable_incident
from backend.features.playbooks import service as playbooks_service


def fetch_incident_playbook(database_session: Session, incident_id: UUID) -> IncidentPlaybookRead:
    """Retourne le playbook de l'incident avec l'état de chaque étape (`playbook=None` s'il n'en a pas).

    Lève ResourceNotFoundError si l'incident n'existe pas.
    """
    return _build_incident_playbook(database_session, fetch_existing_incident(database_session, incident_id))


def change_incident_playbook_step_completion(
    database_session: Session,
    incident_id: UUID,
    step_id: UUID,
    completion_request: IncidentPlaybookStepCompletionRequest,
) -> IncidentPlaybookRead:
    """Coche (`realisee=true`) ou décoche une étape du playbook de l'incident.

    Lève ResourceNotFoundError (incident absent, ou étape n'appartenant pas à son playbook), BusinessRuleViolationError
    (incident sans playbook), ResourceConflictError (incident clôturé).
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    if incident.playbook_id is None:
        raise BusinessRuleViolationError("Cet incident n'a pas de playbook : attribuez-en un avant de suivre ses étapes.")
    playbook = playbooks_service.fetch_playbook_detail(database_session, incident.playbook_id)
    step = next((playbook_step for playbook_step in playbook.etapes if playbook_step.id == step_id), None)
    if step is None:
        raise ResourceNotFoundError(f"L'étape {step_id} n'appartient pas au playbook de cet incident.")

    was_completed = step_id in repository.fetch_completed_step_ids_by_incident_id(database_session, [incident.id])[
        incident.id
    ]
    if completion_request.realisee and not was_completed:
        repository.insert_step_completion_unless_exists(
            database_session, incident.id, step_id, completion_request.realisee_par
        )
    elif not completion_request.realisee and was_completed:
        repository.delete_step_completion(database_session, incident.id, step_id)

    if was_completed != completion_request.realisee:
        incident.updated_at = func.now()
        record_incident_audit_event(
            database_session,
            incident,
            AuditEventType.INCIDENT_UPDATED,
            f"étape {step.ordre} « {step.titre} » {'réalisée' if completion_request.realisee else 'à refaire'}.",
            {"champ": "etape_playbook", "etape_playbook_id": str(step_id), "realisee": completion_request.realisee},
            acteur=completion_request.realisee_par,
        )
    database_session.commit()
    return _build_incident_playbook(database_session, incident)


def _build_incident_playbook(database_session: Session, incident: Incident) -> IncidentPlaybookRead:
    reference = format_incident_reference(incident.numero_reference)
    if incident.playbook_id is None:
        return IncidentPlaybookRead(incident_id=incident.id, reference=reference, playbook=None)
    playbook = playbooks_service.fetch_playbook_detail(database_session, incident.playbook_id)
    completions_by_step_id = {
        completion.etape_playbook_id: completion
        for completion in repository.fetch_step_completions_for_incident(database_session, incident.id)
    }
    steps_progress = [
        IncidentPlaybookStepProgressRead(
            id=step.id,
            ordre=step.ordre,
            titre=step.titre,
            description=step.description,
            est_realisee=step.id in completions_by_step_id,
            realisee_le=completions_by_step_id[step.id].realisee_le if step.id in completions_by_step_id else None,
            realisee_par=completions_by_step_id[step.id].realisee_par if step.id in completions_by_step_id else None,
        )
        for step in playbook.etapes
    ]
    return IncidentPlaybookRead(
        incident_id=incident.id,
        reference=reference,
        playbook=IncidentPlaybookProgressRead(
            playbook_id=playbook.id,
            nom=playbook.nom,
            description=playbook.description,
            categorie=playbook.categorie,
            source=playbook.source,
            nombre_etapes=len(steps_progress),
            nombre_etapes_realisees=sum(1 for step_progress in steps_progress if step_progress.est_realisee),
            etapes=steps_progress,
        ),
    )
