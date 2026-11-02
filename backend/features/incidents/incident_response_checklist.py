"""Suggested response checklist stored independently for every incident."""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.features.audit_journal.models import AuditEventType
from backend.features.incidents import repository
from backend.features.incidents.incident_audit_trail import record_incident_audit_event
from backend.features.incidents.models import Incident, IncidentResponseChecklistItem, IncidentStatus
from backend.features.incidents.schemas import (
    IncidentResponseChecklistCompletionRequest,
    IncidentResponseChecklistItemRead,
)

INCIDENT_RESPONSE_CHECKLIST_DEFINITIONS = (
    (
        "documenter_les_faits",
        "Documenter les faits",
        "Machine, utilisateur, preuve (alerte, inventaire logiciel).",
    ),
    (
        "faire_cesser_l_usage_non_conforme",
        "Faire cesser l’usage non conforme",
        "Appliquer la mesure validée et préserver les éléments utiles à l’analyse.",
    ),
    (
        "informer_hierarchie_et_ressources_humaines",
        "Informer la hiérarchie et les ressources humaines",
        "Transmettre les faits aux interlocuteurs concernés selon les règles internes.",
    ),
    (
        "preserver_les_preuves",
        "Préserver les preuves",
        "Horodater les éléments collectés et noter leur origine et leurs conditions de conservation.",
    ),
    (
        "evaluer_impact",
        "Évaluer l’impact",
        "Repérer les comptes, équipements, données et services potentiellement concernés.",
    ),
    (
        "definir_actions_correctives",
        "Définir les actions correctives",
        "Noter les mesures autorisées, les responsables et les vérifications attendues.",
    ),
    (
        "verifier_retour_a_la_normale",
        "Vérifier le retour à la normale",
        "Consigner les contrôles réalisés et les risques restant à suivre.",
    ),
)


def initialize_incident_response_checklist(database_session: Session, incident_id: UUID) -> None:
    """Add the standard suggested tasks to a newly created incident transaction."""
    repository.insert_response_checklist_items(
        database_session,
        [
            IncidentResponseChecklistItem(
                incident_id=incident_id,
                ordre=position,
                cle=key,
                titre=title,
                description=description,
            )
            for position, (key, title, description) in enumerate(INCIDENT_RESPONSE_CHECKLIST_DEFINITIONS, start=1)
        ],
    )


def fetch_incident_response_checklist(
    database_session: Session, incident_id: UUID
) -> list[IncidentResponseChecklistItemRead]:
    """Return the response checklist for an incident, or raise if the incident does not exist."""
    if repository.fetch_incident_by_id(database_session, incident_id) is None:
        raise ResourceNotFoundError(f"Incident {incident_id} introuvable.")
    return [
        IncidentResponseChecklistItemRead.model_validate(item)
        for item in repository.fetch_response_checklist_items_for_incident(database_session, incident_id)
    ]


def change_incident_response_checklist_completion(
    database_session: Session,
    incident_id: UUID,
    checklist_item_id: UUID,
    completion_request: IncidentResponseChecklistCompletionRequest,
) -> list[IncidentResponseChecklistItemRead]:
    """Update a suggested task, trace effective changes, and return the refreshed checklist."""
    incident = repository.fetch_incident_by_id(database_session, incident_id, is_locked_for_update=True)
    if incident is None:
        raise ResourceNotFoundError(f"Incident {incident_id} introuvable.")
    if incident.statut == IncidentStatus.CLOSED:
        raise ResourceConflictError("Un incident clôturé est en lecture seule : rouvrez-le pour modifier son plan.")

    checklist_item = repository.fetch_response_checklist_item(
        database_session, incident_id, checklist_item_id, is_locked_for_update=True
    )
    if checklist_item is None:
        raise ResourceNotFoundError(f"Élément de checklist {checklist_item_id} introuvable pour cet incident.")

    was_completed = checklist_item.terminee_le is not None
    if was_completed != completion_request.terminee:
        checklist_item.terminee_le = func.now() if completion_request.terminee else None
        checklist_item.terminee_par = completion_request.terminee_par if completion_request.terminee else None
        incident.updated_at = func.now()
        record_incident_audit_event(
            database_session,
            incident,
            AuditEventType.INCIDENT_UPDATED,
            f"action « {checklist_item.titre} » {'terminée' if completion_request.terminee else 'à reprendre'}.",
            {
                "champ": "checklist_reponse",
                "cle": checklist_item.cle,
                "terminee": completion_request.terminee,
            },
            acteur=completion_request.terminee_par,
        )

    database_session.commit()
    return fetch_incident_response_checklist(database_session, incident_id)
