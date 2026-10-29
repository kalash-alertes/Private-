"""Tests du service `source_logs` : insertion idempotente, validation, consultation et filtres.

Toutes les données sont synthétiques (voir tests/synthetic_data.py).
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.core.criticality import CriticalityLevel
from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginationParameters
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.schemas import ImportRunFinishedOutcome
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.models import SourceLog
from backend.features.source_logs.schemas import NewSourceLogData, SourceLogListFilters
from tests.synthetic_data import SYNTHETIC_EVENT_DATE, build_synthetic_new_source_log, store_synthetic_source_log


def count_stored_source_logs(database_session) -> int:
    return database_session.scalar(select(func.count()).select_from(SourceLog))


def test_new_source_log_is_inserted_with_its_source_criticality(database_session) -> None:
    storage_result = store_synthetic_source_log(database_session, criticite_source=CriticalityLevel.HIGH)

    stored_source_log = source_logs_service.fetch_source_log_detail(database_session, storage_result.source_log_id)
    assert storage_result.was_inserted is True
    assert stored_source_log.criticite_source == CriticalityLevel.HIGH
    assert stored_source_log.date_evenement == SYNTHETIC_EVENT_DATE
    assert stored_source_log.donnees_brutes["origine"] == "donnees_synthetiques_de_test"


def test_replaying_the_same_source_identifier_never_creates_a_duplicate(database_session) -> None:
    first_result = store_synthetic_source_log(database_session, "0042", criticite_source=CriticalityLevel.CRITICAL)
    first_source_log = source_logs_service.fetch_source_log_detail(database_session, first_result.source_log_id)

    # Même événement revu par un import ultérieur, avec une criticité différente : il doit être ignoré tel quel.
    later_import_run = import_runs_service.start_import_run(database_session)
    replay_result = source_logs_service.store_source_log_if_new(
        database_session,
        build_synthetic_new_source_log(later_import_run.id, "0042", criticite_source=CriticalityLevel.LOW),
    )
    second_replay_result = source_logs_service.store_source_log_if_new(
        database_session, build_synthetic_new_source_log(later_import_run.id, "0042")
    )

    unchanged_source_log = source_logs_service.fetch_source_log_detail(database_session, first_result.source_log_id)
    assert replay_result.was_inserted is False and second_replay_result.was_inserted is False
    assert replay_result.source_log_id == first_result.source_log_id
    assert count_stored_source_logs(database_session) == 1
    assert unchanged_source_log.criticite_source == CriticalityLevel.CRITICAL
    assert unchanged_source_log.execution_import_id == first_source_log.execution_import_id


def test_logs_cannot_be_attached_to_a_finished_or_unknown_import_run(database_session) -> None:
    import_run = import_runs_service.start_import_run(database_session)
    import_runs_service.finish_import_run(
        database_session,
        import_run.id,
        ImportRunFinishedOutcome(statut="reussie", nb_logs_recus=0, nb_logs_inseres=0, nb_logs_ignores=0),
    )

    with pytest.raises(ResourceConflictError):
        source_logs_service.store_source_log_if_new(database_session, build_synthetic_new_source_log(import_run.id))
    with pytest.raises(ResourceNotFoundError):
        source_logs_service.store_source_log_if_new(database_session, build_synthetic_new_source_log(uuid4()))
    assert count_stored_source_logs(database_session) == 0


def test_event_date_is_converted_to_utc_and_must_have_a_timezone() -> None:
    paris_summer_time = timezone(timedelta(hours=2))
    new_source_log = build_synthetic_new_source_log(
        uuid4(), date_evenement=datetime(2026, 10, 1, 10, 30, tzinfo=paris_summer_time)
    )

    assert new_source_log.date_evenement == datetime(2026, 10, 1, 8, 30, tzinfo=UTC)
    assert new_source_log.date_evenement.utcoffset() == timedelta(0)
    with pytest.raises(ValidationError):
        build_synthetic_new_source_log(uuid4(), date_evenement=datetime(2026, 10, 1, 8, 30))


@pytest.mark.parametrize(
    "invalid_field_values",
    [
        pytest.param({"identifiant_source": "   "}, id="identifiant_vide"),
        pytest.param({"identifiant_source": "x" * 256}, id="identifiant_trop_long"),
        pytest.param({"type": ""}, id="type_vide"),
        pytest.param({"criticite_source": "inconnue"}, id="criticite_inconnue"),
        pytest.param({"champ_inattendu": "x"}, id="champ_inconnu"),
    ],
)
def test_invalid_new_source_log_is_rejected(invalid_field_values) -> None:
    valid_field_values = build_synthetic_new_source_log(uuid4()).model_dump()
    with pytest.raises(ValidationError):
        NewSourceLogData(**(valid_field_values | invalid_field_values))


def test_source_logs_list_applies_filters_and_pagination(database_session) -> None:
    import_run = import_runs_service.start_import_run(database_session)
    for day_offset, criticality in enumerate([CriticalityLevel.CRITICAL, CriticalityLevel.CRITICAL, CriticalityLevel.HIGH]):
        source_logs_service.store_source_log_if_new(
            database_session,
            build_synthetic_new_source_log(
                import_run.id,
                f"liste-{day_offset}",
                criticite_source=criticality,
                date_evenement=SYNTHETIC_EVENT_DATE + timedelta(days=day_offset),
            ),
        )
    store_synthetic_source_log(database_session, "autre-import", event_type="synthetique_autre")

    def list_logs(pagination=PaginationParameters(), **filter_values):
        return source_logs_service.list_source_logs(database_session, SourceLogListFilters(**filter_values), pagination)

    all_logs = list_logs()
    assert all_logs.total == 4
    # Les événements les plus récents d'abord.
    event_dates = [item.date_evenement for item in all_logs.items]
    assert event_dates == sorted(event_dates, reverse=True)
    assert list_logs(criticite_source="critique").total == 3
    assert list_logs(execution_import_id=import_run.id).total == 3
    assert list_logs(type="synthetique_autre").total == 1
    dated_page = list_logs(
        date_evenement_min=SYNTHETIC_EVENT_DATE + timedelta(days=1), date_evenement_max=SYNTHETIC_EVENT_DATE + timedelta(days=2)
    )
    assert {item.identifiant_source for item in dated_page.items} == {"SYNTHETIQUE-liste-1", "SYNTHETIQUE-liste-2"}
    assert len(list_logs(PaginationParameters(limit=3, offset=3)).items) == 1


def test_inverted_date_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceLogListFilters(date_evenement_min=SYNTHETIC_EVENT_DATE, date_evenement_max=SYNTHETIC_EVENT_DATE - timedelta(1))


def test_fetching_unknown_source_log_raises_not_found(database_session) -> None:
    with pytest.raises(ResourceNotFoundError):
        source_logs_service.fetch_source_log_metadata(database_session, uuid4())
