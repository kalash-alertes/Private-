"""Tests du suivi d'incident ajouté avec les Paramètres : référence, onglets, recherche, délais, playbook, escalade.

Données synthétiques. Pour simuler un incident ancien, sa date de création est reculée directement en base.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from backend.core.criticality import CriticalityLevel
from backend.core.domain_errors import BusinessRuleViolationError, ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import AuditEventListFilters
from backend.features.dashboard import service as dashboard_service
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incident_response_settings.schemas import ResponseDeadlineRuleUpdateRequest
from backend.features.incidents import automatic_escalation, incident_playbook_progress
from backend.features.incidents import service as incidents_service
from backend.features.incidents.models import Incident
from backend.features.incidents.schemas import (
    IncidentCreationRequest,
    IncidentListFilters,
    IncidentListView,
    IncidentPlaybookAssignmentRequest,
    IncidentPlaybookStepCompletionRequest,
    IncidentStatusChangeRequest,
    IncidentTitleChangeRequest,
)
from backend.features.playbooks import service as playbooks_service
from tests.synthetic_data import build_synthetic_playbook_request, store_synthetic_source_log


def create_incident(database_session, identifier_suffix="0001", **creation_values):
    storage_result = store_synthetic_source_log(database_session, identifier_suffix)
    return incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=storage_result.source_log_id, **creation_values)
    )


def change_status(database_session, incident_id, statut):
    return incidents_service.change_incident_status(database_session, incident_id, IncidentStatusChangeRequest(statut=statut))


def move_incident_creation_back(database_session, incident_id, elapsed: timedelta) -> None:
    database_session.execute(
        update(Incident).where(Incident.id == incident_id).values(created_at=datetime.now(UTC) - elapsed)
    )
    database_session.commit()


def set_rule(database_session, criticality, delay_minutes, is_escalation_enabled=False, escalation_target=None) -> None:
    incident_response_settings_service.update_response_deadline_rule(
        database_session,
        criticality,
        ResponseDeadlineRuleUpdateRequest(
            delai_traitement_minutes=delay_minutes,
            escalade_automatique_activee=is_escalation_enabled,
            escalader_vers=escalation_target,
        ),
    )


def test_incidents_get_sequential_references_and_defaults_from_the_log(database_session) -> None:
    first_incident = create_incident(database_session, "ref-1")
    second_incident = create_incident(database_session, "ref-2", titre="Titre choisi", categorie="phishing")

    assert (first_incident.reference, second_incident.reference) == ("INC-000001", "INC-000002")
    assert first_incident.titre == "Alerte synthetique_intrusion"
    assert first_incident.categorie == "synthetique_intrusion"
    assert (second_incident.titre, second_incident.categorie) == ("Titre choisi", "phishing")
    assert first_incident.nombre_alertes == 1 and first_incident.alertes[0].log_id == first_incident.log_id
    assert first_incident.est_ouvert is True


def test_playbook_of_the_category_is_assigned_automatically(database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())

    incident = create_incident(database_session)
    incident_of_other_category = create_incident(database_session, "autre", categorie="autre_categorie")

    assert incident.playbook_id == playbook.id
    assert incident.plan.nom == playbook.nom and incident.plan.nombre_etapes == 3
    assert incident.plan.nombre_etapes_realisees == 0
    assert incident_of_other_category.plan is None


def test_tabs_split_open_and_handled_incidents_and_search_matches_text(database_session) -> None:
    open_incident = create_incident(database_session, "a", titre="Scan de ports 100%")
    handled_incident = create_incident(database_session, "b", titre="Connexion suspecte")
    change_status(database_session, handled_incident.id, "resolu")

    def list_ids(**filter_values):
        page = incidents_service.list_incidents(database_session, IncidentListFilters(**filter_values), PaginationParameters())
        return [item.id for item in page.items]

    assert list_ids(vue=IncidentListView.IN_PROGRESS) == [open_incident.id]
    assert list_ids(vue=IncidentListView.HANDLED) == [handled_incident.id]
    assert list_ids(recherche="SCAN") == [open_incident.id]
    # Les caractères spéciaux de LIKE sont cherchés littéralement.
    assert list_ids(recherche="100%") == [open_incident.id]
    assert list_ids(recherche="%") == [open_incident.id]
    # `_` n'est pas un joker : « Scan_de » ne trouve pas « Scan de ».
    assert list_ids(recherche="Scan_de") == []


def test_handled_date_follows_the_status(database_session) -> None:
    incident = create_incident(database_session)

    resolved_incident = change_status(database_session, incident.id, "resolu")
    closed_incident = change_status(database_session, incident.id, "cloture")
    reopened_incident = change_status(database_session, incident.id, "en_cours")

    assert resolved_incident.traite_le is not None and resolved_incident.est_ouvert is False
    # Passer de résolu à clôturé ne change pas la date de traitement.
    assert closed_incident.traite_le == resolved_incident.traite_le
    assert reopened_incident.traite_le is None and reopened_incident.est_ouvert is True


def test_deadline_depends_on_the_current_criticality(database_session) -> None:
    incident = create_incident(database_session)  # criticité critique : 60 minutes par défaut
    assert incident.delai_depasse is False
    assert incident.date_limite_traitement == incident.created_at + timedelta(minutes=60)

    move_incident_creation_back(database_session, incident.id, timedelta(hours=2))
    assert incidents_service.fetch_incident_detail(database_session, incident.id).delai_depasse is True

    set_rule(database_session, CriticalityLevel.CRITICAL, delay_minutes=24 * 60)
    assert incidents_service.fetch_incident_detail(database_session, incident.id).delai_depasse is False


def test_playbook_steps_can_be_completed_and_undone(database_session) -> None:
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    incident = create_incident(database_session)
    first_step_id = incident_playbook_progress.fetch_incident_playbook(database_session, incident.id).playbook.etapes[0].id

    def complete_step(is_completed: bool, step_id=first_step_id):
        return incident_playbook_progress.change_incident_playbook_step_completion(
            database_session,
            incident.id,
            step_id,
            IncidentPlaybookStepCompletionRequest(realisee=is_completed, realisee_par="analyste.synthetique"),
        )

    completed_view = complete_step(True)
    complete_step(True)  # cocher deux fois ne change rien

    assert completed_view.playbook.nombre_etapes_realisees == 1
    assert completed_view.playbook.etapes[0].est_realisee is True
    assert completed_view.playbook.etapes[0].realisee_par == "analyste.synthetique"
    assert incidents_service.fetch_incident_detail(database_session, incident.id).plan.nombre_etapes_realisees == 1
    assert complete_step(False).playbook.nombre_etapes_realisees == 0

    with pytest.raises(ResourceNotFoundError):
        complete_step(True, step_id=incident.id)  # un id qui n'est pas une étape de ce playbook
    change_status(database_session, incident.id, "cloture")
    with pytest.raises(ResourceConflictError):
        complete_step(True)


def test_step_completion_requires_a_playbook(database_session) -> None:
    incident = create_incident(database_session)

    assert incident_playbook_progress.fetch_incident_playbook(database_session, incident.id).playbook is None
    with pytest.raises(BusinessRuleViolationError):
        incident_playbook_progress.change_incident_playbook_step_completion(
            database_session, incident.id, incident.id, IncidentPlaybookStepCompletionRequest(realisee=True)
        )


def test_playbook_can_be_changed_and_deleting_it_detaches_incidents(database_session, database_session_factory) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(categorie=None))
    incident = create_incident(database_session)

    assigned_incident = incidents_service.change_incident_playbook(
        database_session, incident.id, IncidentPlaybookAssignmentRequest(playbook_id=playbook.id)
    )
    assert assigned_incident.plan.playbook_id == playbook.id
    with pytest.raises(ResourceNotFoundError):
        incidents_service.change_incident_playbook(
            database_session, incident.id, IncidentPlaybookAssignmentRequest(playbook_id=incident.id)
        )

    playbooks_service.delete_playbook(database_session, playbook.id)
    with database_session_factory() as new_database_session:
        detached_incident = incidents_service.fetch_incident_detail(new_database_session, incident.id)
    assert detached_incident.playbook_id is None and detached_incident.plan is None


def test_overdue_incidents_are_escalated_once(database_session) -> None:
    set_rule(database_session, CriticalityLevel.CRITICAL, 60, is_escalation_enabled=True, escalation_target="n2.soc")
    overdue_incident = create_incident(database_session, "en-retard")
    recent_incident = create_incident(database_session, "recent")
    handled_overdue_incident = create_incident(database_session, "traite")
    change_status(database_session, handled_overdue_incident.id, "resolu")
    for incident_id in (overdue_incident.id, handled_overdue_incident.id):
        move_incident_creation_back(database_session, incident_id, timedelta(hours=3))

    first_run = automatic_escalation.escalate_overdue_incidents(database_session)
    second_run = automatic_escalation.escalate_overdue_incidents(database_session)

    assert first_run.incidents_escalades == [overdue_incident.id]
    assert second_run.nombre_incidents_escalades == 0
    escalated_incident = incidents_service.fetch_incident_detail(database_session, overdue_incident.id)
    assert escalated_incident.escalade_le is not None and escalated_incident.assigne_a == "n2.soc"
    assert incidents_service.fetch_incident_detail(database_session, recent_incident.id).escalade_le is None
    escalation_events = audit_journal_service.list_audit_events(
        database_session, AuditEventListFilters(type_evenement=AuditEventType.INCIDENT_ESCALATED), PaginationParameters()
    )
    assert escalation_events.total == 1 and escalation_events.items[0].acteur is None


def test_escalation_does_nothing_when_disabled(database_session) -> None:
    incident = create_incident(database_session)
    move_incident_creation_back(database_session, incident.id, timedelta(days=2))

    assert automatic_escalation.escalate_overdue_incidents(database_session).nombre_incidents_escalades == 0


def test_every_effective_change_is_audited(database_session) -> None:
    incident = create_incident(database_session)
    incidents_service.change_incident_title(database_session, incident.id, IncidentTitleChangeRequest(titre="Nouveau"))
    incidents_service.change_incident_title(database_session, incident.id, IncidentTitleChangeRequest(titre="Nouveau"))
    change_status(database_session, incident.id, "en_cours")

    history = audit_journal_service.list_audit_events(
        database_session,
        AuditEventListFilters(type_ressource="incident", identifiant_ressource=str(incident.id)),
        PaginationParameters(),
    )
    # Comparaison sans ordre : des événements de la même seconde n'ont pas d'ordre garanti (SQLite : précision 1 s).
    assert sorted(event.type_evenement for event in history.items) == sorted(
        [AuditEventType.INCIDENT_CREATED, AuditEventType.INCIDENT_UPDATED, AuditEventType.INCIDENT_UPDATED]
    )
    assert all(event.description.startswith("INC-000001") for event in history.items)


def test_dashboard_counts_incidents_and_alerts(database_session) -> None:
    store_synthetic_source_log(database_session, "sans-incident")
    open_incident = create_incident(database_session, "ouvert")
    handled_incident = create_incident(database_session, "traite")
    change_status(database_session, handled_incident.id, "cloture")
    move_incident_creation_back(database_session, open_incident.id, timedelta(hours=5))

    dashboard = dashboard_service.build_dashboard(database_session)

    assert dashboard.nombre_alertes == 3 and dashboard.nombre_alertes_a_traiter == 1
    assert (dashboard.nombre_incidents_ouverts, dashboard.nombre_incidents_traites) == (1, 1)
    assert dashboard.nombre_incidents_ouverts_delai_depasse == 1
    assert dashboard.incidents_ouverts_par_criticite[CriticalityLevel.CRITICAL] == 1
    assert dashboard.temps_moyen_traitement_minutes is not None
    assert len(dashboard.activite) == 7
    assert dashboard.activite[-1].incidents_traites == 1
