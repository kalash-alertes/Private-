"""Tests for incident-specific response checklist persistence and validation."""

from uuid import uuid4

import pytest

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.features.incidents import incident_response_checklist, service as incidents_service
from backend.features.incidents.schemas import (
    IncidentCreationRequest,
    IncidentResponseChecklistCompletionRequest,
    IncidentStatusChangeRequest,
)
from tests.synthetic_data import store_synthetic_source_log


def create_incident_with_response_checklist(database_session):
    """Create a synthetic incident with its default response checklist."""
    stored_log = store_synthetic_source_log(database_session, identifier_suffix="response-checklist-service")
    return incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=stored_log.source_log_id)
    )


def test_new_incident_gets_seven_persisted_response_tasks(database_session) -> None:
    incident = create_incident_with_response_checklist(database_session)

    checklist = incident_response_checklist.fetch_incident_response_checklist(database_session, incident.id)

    assert [item.titre for item in checklist] == [
        "Documenter les faits",
        "Faire cesser l’usage non conforme",
        "Informer la hiérarchie et les ressources humaines",
        "Préserver les preuves",
        "Évaluer l’impact",
        "Définir les actions correctives",
        "Vérifier le retour à la normale",
    ]
    assert checklist[0].description == "Machine, utilisateur, preuve (alerte, inventaire logiciel)."


def test_response_task_can_be_completed_and_reopened(database_session) -> None:
    incident = create_incident_with_response_checklist(database_session)
    checklist = incident_response_checklist.fetch_incident_response_checklist(database_session, incident.id)
    completion_request = IncidentResponseChecklistCompletionRequest(terminee=True, terminee_par="analyste.synthetique")

    completed_checklist = incident_response_checklist.change_incident_response_checklist_completion(
        database_session, incident.id, checklist[0].id, completion_request
    )
    assert completed_checklist[0].terminee_le is not None
    assert completed_checklist[0].terminee_par == "analyste.synthetique"

    reopened_checklist = incident_response_checklist.change_incident_response_checklist_completion(
        database_session,
        incident.id,
        checklist[0].id,
        IncidentResponseChecklistCompletionRequest(terminee=False),
    )
    assert reopened_checklist[0].terminee_le is None
    assert reopened_checklist[0].terminee_par is None


def test_closed_incident_response_checklist_is_read_only(database_session) -> None:
    incident = create_incident_with_response_checklist(database_session)
    checklist = incident_response_checklist.fetch_incident_response_checklist(database_session, incident.id)
    incidents_service.change_incident_status(database_session, incident.id, IncidentStatusChangeRequest(statut="cloture"))

    with pytest.raises(ResourceConflictError):
        incident_response_checklist.change_incident_response_checklist_completion(
            database_session,
            incident.id,
            checklist[0].id,
            IncidentResponseChecklistCompletionRequest(terminee=True),
        )


def test_response_checklist_rejects_an_item_from_another_incident(database_session) -> None:
    incident = create_incident_with_response_checklist(database_session)

    with pytest.raises(ResourceNotFoundError):
        incident_response_checklist.change_incident_response_checklist_completion(
            database_session,
            incident.id,
            uuid4(),
            IncidentResponseChecklistCompletionRequest(terminee=True),
        )
