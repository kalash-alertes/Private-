"""Tests du journal d'audit : enregistrement dans la transaction de l'appelant, filtres, route en lecture seule."""

from datetime import UTC, datetime, timedelta

from backend.core.pagination import PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import AuditEventListFilters, NewAuditEventData


def record_event(database_session, event_type: AuditEventType, acteur: str | None = None) -> None:
    audit_journal_service.record_audit_event(
        database_session, NewAuditEventData(type_evenement=event_type, description="Événement synthétique", acteur=acteur)
    )


def test_event_is_kept_only_if_the_caller_commits(database_session) -> None:
    record_event(database_session, AuditEventType.LOGIN_FAILED)
    database_session.rollback()
    record_event(database_session, AuditEventType.LOGIN_SUCCEEDED, acteur="analyste.synthetique")
    database_session.commit()

    page = audit_journal_service.list_audit_events(database_session, AuditEventListFilters(), PaginationParameters())
    assert [event.type_evenement for event in page.items] == [AuditEventType.LOGIN_SUCCEEDED]


def test_events_can_be_filtered(database_session) -> None:
    record_event(database_session, AuditEventType.LOGIN_FAILED, acteur="inconnu")
    record_event(database_session, AuditEventType.LOGIN_SUCCEEDED, acteur="analyste.synthetique")
    database_session.commit()

    def count_events(**filter_values) -> int:
        return audit_journal_service.list_audit_events(
            database_session, AuditEventListFilters(**filter_values), PaginationParameters()
        ).total

    assert count_events() == 2
    assert count_events(type_evenement=AuditEventType.LOGIN_FAILED) == 1
    assert count_events(acteur="analyste.synthetique") == 1
    assert count_events(date_evenement_min=datetime.now(UTC) + timedelta(days=1)) == 0


def test_audit_journal_route_is_read_only(api_client) -> None:
    assert api_client.get("/parametres/journal-audit").status_code == 200
    assert api_client.get("/parametres/journal-audit?type_evenement=inconnu").status_code == 422
    assert api_client.post("/parametres/journal-audit", json={}).status_code == 405
