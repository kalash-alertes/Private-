"""Tests du service `incidents` : création, unicité par log, clôture / réouverture, règles provisoires.

Toutes les données sont synthétiques (voir tests/synthetic_data.py).
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.core.criticality import CriticalityLevel
from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginationParameters
from backend.features.incidents import service as incidents_service
from backend.features.incidents.models import IncidentStatus
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCriticalityChangeRequest,
    IncidentFalsePositiveQualificationRequest,
    IncidentListFilters,
    IncidentStatusChangeRequest,
)
from backend.features.source_logs import service as source_logs_service
from tests.synthetic_data import store_synthetic_source_log


def create_synthetic_incident(database_session, identifier_suffix="0001", criticite_source=CriticalityLevel.CRITICAL):
    storage_result = store_synthetic_source_log(database_session, identifier_suffix, criticite_source=criticite_source)
    return incidents_service.create_incident_from_source_log(database_session, storage_result.source_log_id)


def change_status(database_session, incident_id, statut):
    return incidents_service.change_incident_status(
        database_session, incident_id, IncidentStatusChangeRequest(statut=statut)
    )


def test_new_incident_starts_with_the_source_criticality(database_session) -> None:
    incident = create_synthetic_incident(database_session, criticite_source=CriticalityLevel.HIGH)

    assert incident.statut == IncidentStatus.NEW
    assert incident.criticite_actuelle == CriticalityLevel.HIGH
    assert incident.criticite_source == CriticalityLevel.HIGH
    assert incident.faux_positif is False and incident.justification is None
    assert incident.assigne_a is None and incident.closed_at is None


def test_a_log_gives_at_most_one_incident(database_session, database_session_factory) -> None:
    incident = create_synthetic_incident(database_session)

    # Seconde création depuis une autre session : passe par la contrainte UNIQUE (même chemin qu'une course).
    with database_session_factory() as other_database_session:
        with pytest.raises(ResourceConflictError):
            incidents_service.create_incident_from_source_log(other_database_session, incident.log_id)
        # La session reste utilisable après le conflit (SAVEPOINT annulé, pas la transaction entière).
        assert incidents_service.fetch_incident_detail(other_database_session, incident.id).id == incident.id


def test_incident_cannot_be_created_from_unknown_log(database_session) -> None:
    with pytest.raises(ResourceNotFoundError):
        incidents_service.create_incident_from_source_log(database_session, uuid4())


def test_criticality_reevaluation_never_touches_the_source_criticality(database_session) -> None:
    incident = create_synthetic_incident(database_session, criticite_source=CriticalityLevel.CRITICAL)

    lowered_incident = incidents_service.change_incident_current_criticality(
        database_session, incident.id, IncidentCriticalityChangeRequest(criticite_actuelle="faible")
    )
    raised_incident = incidents_service.change_incident_current_criticality(
        database_session, incident.id, IncidentCriticalityChangeRequest(criticite_actuelle="haute")
    )

    assert lowered_incident.criticite_actuelle == CriticalityLevel.LOW
    assert raised_incident.criticite_actuelle == CriticalityLevel.HIGH
    assert raised_incident.criticite_source == CriticalityLevel.CRITICAL
    source_log = source_logs_service.fetch_source_log_metadata(database_session, incident.log_id)
    assert source_log.criticite_source == CriticalityLevel.CRITICAL


def test_closing_sets_closed_at_and_reopening_clears_it(database_session) -> None:
    incident = create_synthetic_incident(database_session)

    closed_incident = change_status(database_session, incident.id, "cloture")
    closed_again_incident = change_status(database_session, incident.id, "cloture")
    reopened_incident = change_status(database_session, incident.id, "en_cours")

    assert closed_incident.closed_at is not None
    assert closed_incident.closed_at >= closed_incident.created_at
    # Reclôturer un incident déjà clôturé ne change pas sa date de clôture.
    assert closed_again_incident.closed_at == closed_incident.closed_at
    assert reopened_incident.statut == IncidentStatus.IN_PROGRESS
    assert reopened_incident.closed_at is None


def test_any_status_transition_is_currently_allowed(database_session) -> None:
    # Règle PROVISOIRE : aucun graphe de transitions n'est encore défini (décision attendue).
    incident = create_synthetic_incident(database_session)
    for statut in ["resolu", "nouveau", "en_attente", "cloture", "nouveau"]:
        assert change_status(database_session, incident.id, statut).statut == statut


def test_closed_incident_is_read_only_until_reopened(database_session) -> None:
    incident = create_synthetic_incident(database_session)
    change_status(database_session, incident.id, "cloture")

    with pytest.raises(ResourceConflictError):
        incidents_service.change_incident_current_criticality(
            database_session, incident.id, IncidentCriticalityChangeRequest(criticite_actuelle="faible")
        )
    with pytest.raises(ResourceConflictError):
        incidents_service.change_incident_assignment(
            database_session, incident.id, IncidentAssignmentRequest(assigne_a="analyste.synthetique")
        )
    with pytest.raises(ResourceConflictError):
        incidents_service.change_incident_false_positive_qualification(
            database_session,
            incident.id,
            IncidentFalsePositiveQualificationRequest(faux_positif=True, justification="trop tard"),
        )

    change_status(database_session, incident.id, "en_cours")
    assigned_incident = incidents_service.change_incident_assignment(
        database_session, incident.id, IncidentAssignmentRequest(assigne_a="analyste.synthetique")
    )
    assert assigned_incident.assigne_a == "analyste.synthetique"


def test_false_positive_requires_a_justification() -> None:
    with pytest.raises(ValidationError):
        IncidentFalsePositiveQualificationRequest(faux_positif=True)
    with pytest.raises(ValidationError):
        IncidentFalsePositiveQualificationRequest(faux_positif=True, justification="   ")


def test_false_positive_qualification_and_withdrawal(database_session) -> None:
    incident = create_synthetic_incident(database_session)

    qualified_incident = incidents_service.change_incident_false_positive_qualification(
        database_session,
        incident.id,
        IncidentFalsePositiveQualificationRequest(faux_positif=True, justification="  Scan interne planifié  "),
    )
    withdrawn_without_reason = incidents_service.change_incident_false_positive_qualification(
        database_session, incident.id, IncidentFalsePositiveQualificationRequest(faux_positif=False)
    )
    withdrawn_with_reason = incidents_service.change_incident_false_positive_qualification(
        database_session,
        incident.id,
        IncidentFalsePositiveQualificationRequest(faux_positif=False, justification="Scan non planifié en réalité"),
    )

    assert qualified_incident.faux_positif is True
    assert qualified_incident.justification == "Scan interne planifié"
    # Retrait sans justification : la précédente est conservée comme trace (pas d'historique en V1).
    assert withdrawn_without_reason.faux_positif is False
    assert withdrawn_without_reason.justification == "Scan interne planifié"
    assert withdrawn_with_reason.justification == "Scan non planifié en réalité"
    # Le statut n'est pas modifié par la qualification (règle non encore décidée).
    assert withdrawn_with_reason.statut == IncidentStatus.NEW


def test_assignment_and_unassignment(database_session) -> None:
    incident = create_synthetic_incident(database_session)

    assigned_incident = incidents_service.change_incident_assignment(
        database_session, incident.id, IncidentAssignmentRequest(assigne_a="  analyste.synthetique  ")
    )
    unassigned_incident = incidents_service.change_incident_assignment(
        database_session, incident.id, IncidentAssignmentRequest(assigne_a=None)
    )

    assert assigned_incident.assigne_a == "analyste.synthetique"
    assert unassigned_incident.assigne_a is None
    with pytest.raises(ValidationError):
        IncidentAssignmentRequest(assigne_a="   ")
    with pytest.raises(ValidationError):
        IncidentAssignmentRequest(assigne_a="x" * 256)


def test_request_that_changes_nothing_keeps_updated_at(database_session) -> None:
    incident = create_synthetic_incident(database_session)

    unchanged_incident = change_status(database_session, incident.id, "nouveau")
    unchanged_incident = incidents_service.change_incident_current_criticality(
        database_session, incident.id, IncidentCriticalityChangeRequest(criticite_actuelle=incident.criticite_actuelle)
    )

    assert unchanged_incident.updated_at == incident.updated_at


def test_modifying_unknown_incident_raises_not_found(database_session) -> None:
    with pytest.raises(ResourceNotFoundError):
        change_status(database_session, uuid4(), "en_cours")
    with pytest.raises(ResourceNotFoundError):
        incidents_service.fetch_incident_detail(database_session, uuid4())


def test_incidents_list_applies_filters_and_pagination(database_session) -> None:
    incidents = [create_synthetic_incident(database_session, f"inc-{index}") for index in range(4)]
    change_status(database_session, incidents[0].id, "en_cours")
    incidents_service.change_incident_assignment(
        database_session, incidents[1].id, IncidentAssignmentRequest(assigne_a="analyste.synthetique")
    )
    incidents_service.change_incident_false_positive_qualification(
        database_session, incidents[2].id, IncidentFalsePositiveQualificationRequest(faux_positif=True, justification="ok")
    )
    incidents_service.change_incident_current_criticality(
        database_session, incidents[3].id, IncidentCriticalityChangeRequest(criticite_actuelle="moyenne")
    )

    def list_ids(pagination=PaginationParameters(), **filter_values):
        page = incidents_service.list_incidents(database_session, IncidentListFilters(**filter_values), pagination)
        return page.total, [item.id for item in page.items]

    assert list_ids()[0] == 4
    assert list_ids(statut="en_cours") == (1, [incidents[0].id])
    assert list_ids(assigne_a="analyste.synthetique") == (1, [incidents[1].id])
    assert list_ids(faux_positif=True) == (1, [incidents[2].id])
    assert list_ids(faux_positif=False)[0] == 3
    assert list_ids(criticite_actuelle="moyenne") == (1, [incidents[3].id])
    assert list_ids(log_id=incidents[3].log_id) == (1, [incidents[3].id])
    first_total, first_page_ids = list_ids(PaginationParameters(limit=3, offset=0))
    _, second_page_ids = list_ids(PaginationParameters(limit=3, offset=3))
    assert len(first_page_ids) == 3 and len(second_page_ids) == 1
    assert set(first_page_ids) | set(second_page_ids) == {incident.id for incident in incidents}
