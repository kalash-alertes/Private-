"""Tests des paramètres de réponse aux incidents (délais et escalade par sévérité) : service et routes."""

from backend.core.criticality import CriticalityLevel
from backend.core.pagination import PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import AuditEventListFilters
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incident_response_settings.schemas import ResponseDeadlineRuleUpdateRequest


def test_migration_creates_one_default_rule_per_criticality(database_session) -> None:
    rules = incident_response_settings_service.list_response_deadline_rules(database_session)

    assert [rule.criticite for rule in rules] == [
        CriticalityLevel.CRITICAL,
        CriticalityLevel.HIGH,
        CriticalityLevel.MEDIUM,
        CriticalityLevel.LOW,
        CriticalityLevel.INFORMATION,
    ]
    assert rules[0].delai_traitement_minutes == 60
    assert not any(rule.escalade_automatique_activee for rule in rules)


def test_rule_update_is_saved_and_audited(database_session) -> None:
    updated_rule = incident_response_settings_service.update_response_deadline_rule(
        database_session,
        CriticalityLevel.HIGH,
        ResponseDeadlineRuleUpdateRequest(
            delai_traitement_minutes=120, escalade_automatique_activee=True, escalader_vers="  responsable.soc  "
        ),
    )
    # Une demande identique ne crée pas de second événement d'audit.
    incident_response_settings_service.update_response_deadline_rule(
        database_session,
        CriticalityLevel.HIGH,
        ResponseDeadlineRuleUpdateRequest(
            delai_traitement_minutes=120, escalade_automatique_activee=True, escalader_vers="responsable.soc"
        ),
    )

    assert updated_rule.delai_traitement_minutes == 120
    assert updated_rule.escalader_vers == "responsable.soc"
    audit_events = audit_journal_service.list_audit_events(
        database_session, AuditEventListFilters(type_evenement=AuditEventType.SETTINGS_UPDATED), PaginationParameters()
    )
    assert audit_events.total == 1
    assert audit_events.items[0].details["apres"]["delai_traitement_minutes"] == 120


def test_rule_routes_validate_input(api_client) -> None:
    assert len(api_client.get("/parametres/reponse-incidents/delais").json()) == 5
    valid_body = {"delai_traitement_minutes": 30, "escalade_automatique_activee": False}
    assert api_client.put("/parametres/reponse-incidents/delais/critique", json=valid_body).status_code == 200
    assert api_client.put("/parametres/reponse-incidents/delais/inconnue", json=valid_body).status_code == 422
    invalid_delay = {**valid_body, "delai_traitement_minutes": 0}
    assert api_client.put("/parametres/reponse-incidents/delais/critique", json=invalid_delay).status_code == 422
    blank_target = {**valid_body, "escalader_vers": "  "}
    assert api_client.put("/parametres/reponse-incidents/delais/critique", json=blank_target).status_code == 422
