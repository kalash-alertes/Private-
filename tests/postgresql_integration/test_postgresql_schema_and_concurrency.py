"""Tests d'intégration PostgreSQL : schéma réel (types, contraintes, migrations) et accès concurrents.

Ignorés si `TEST_POSTGRESQL_DATABASE_URL` n'est pas défini (voir conftest.py). Données synthétiques uniquement.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.core.domain_errors import ResourceConflictError
from backend.database_model_registry import DatabaseModelBase, ImportRun, Incident, SourceLog
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.schemas import ImportRunFinishedOutcome
from backend.features.incidents import service as incidents_service
from backend.features.incidents.schemas import IncidentStatusChangeRequest
from backend.features.source_logs import service as source_logs_service
from tests.synthetic_data import build_synthetic_new_source_log, store_synthetic_source_log

pytestmark = pytest.mark.postgresql

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONCURRENT_WORKER_COUNT = 6


def run_concurrently(task, worker_count: int = CONCURRENT_WORKER_COUNT) -> list:
    """Lance `task(barrier)` dans plusieurs threads qui démarrent ensemble ; retourne résultats ou exceptions."""
    start_barrier = Barrier(worker_count)

    def run_task_and_capture_outcome(_worker_index):
        try:
            return task(start_barrier)
        except Exception as raised_exception:  # noqa: BLE001 - on veut compter chaque issue
            return raised_exception

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(run_task_and_capture_outcome, range(worker_count)))


def test_schema_uses_native_postgresql_types(migrated_postgresql_database_engine) -> None:
    with migrated_postgresql_database_engine.connect() as connection:
        column_types = dict(
            connection.execute(
                text(
                    "SELECT table_name || '.' || column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = current_schema()"
                )
            ).all()
        )

    assert column_types["logs.id"] == "uuid"
    assert column_types["logs.donnees_brutes"] == "jsonb"
    for timestamp_column in ["executions_import.debut", "logs.date_evenement", "incidents.closed_at"]:
        assert column_types[timestamp_column] == "timestamp with time zone"


def test_postgresql_migrations_match_models_and_roundtrip(migrated_postgresql_database_engine) -> None:
    alembic_configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.downgrade(alembic_configuration, "base")
    command.upgrade(alembic_configuration, "head")

    with migrated_postgresql_database_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), DatabaseModelBase.metadata)
    assert differences == []


def test_postgresql_check_constraints_are_enforced(postgresql_session_factory) -> None:
    invalid_rows = [
        ImportRun(statut="reussie", fin=datetime.now(UTC), nb_logs_recus=1, nb_logs_inseres=2),
        ImportRun(statut="echouee", fin=datetime.now(UTC)),
        ImportRun(statut="cloture"),
    ]
    for invalid_row in invalid_rows:
        with postgresql_session_factory() as session:
            session.add(invalid_row)
            with pytest.raises(IntegrityError):
                session.flush()

    with postgresql_session_factory() as session:
        storage_result = store_synthetic_source_log(session)
        session.add(Incident(log_id=storage_result.source_log_id, criticite_actuelle="critique", faux_positif=True))
        with pytest.raises(IntegrityError):
            session.flush()


def test_concurrent_imports_of_the_same_log_store_it_once(postgresql_session_factory) -> None:
    with postgresql_session_factory() as session:
        import_run_id = import_runs_service.start_import_run(session).id

    def store_same_log(start_barrier):
        with postgresql_session_factory() as session:
            start_barrier.wait()
            return source_logs_service.store_source_log_if_new(
                session, build_synthetic_new_source_log(import_run_id, "concurrent")
            )

    storage_results = run_concurrently(store_same_log)

    assert all(not isinstance(result, Exception) for result in storage_results), storage_results
    assert sum(result.was_inserted for result in storage_results) == 1
    assert len({result.source_log_id for result in storage_results}) == 1
    with postgresql_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SourceLog)) == 1


def test_concurrent_incident_creations_for_one_log_create_one_incident(postgresql_session_factory) -> None:
    with postgresql_session_factory() as session:
        log_id = store_synthetic_source_log(session).source_log_id

    def create_incident(start_barrier):
        with postgresql_session_factory() as session:
            start_barrier.wait()
            return incidents_service.create_incident_from_source_log(session, log_id)

    creation_outcomes = run_concurrently(create_incident)

    assert sum(not isinstance(outcome, Exception) for outcome in creation_outcomes) == 1
    assert all(
        isinstance(outcome, ResourceConflictError) for outcome in creation_outcomes if isinstance(outcome, Exception)
    ), creation_outcomes
    with postgresql_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Incident)) == 1


def test_concurrent_finishes_of_one_import_run_keep_the_first_outcome(postgresql_session_factory) -> None:
    with postgresql_session_factory() as session:
        import_run_id = import_runs_service.start_import_run(session).id

    def finish_import_run(start_barrier):
        with postgresql_session_factory() as session:
            start_barrier.wait()
            return import_runs_service.finish_import_run(
                session,
                import_run_id,
                ImportRunFinishedOutcome(statut="reussie", nb_logs_recus=0, nb_logs_inseres=0, nb_logs_ignores=0),
            )

    finish_outcomes = run_concurrently(finish_import_run)

    assert sum(not isinstance(outcome, Exception) for outcome in finish_outcomes) == 1
    assert all(
        isinstance(outcome, ResourceConflictError) for outcome in finish_outcomes if isinstance(outcome, Exception)
    ), finish_outcomes


def test_concurrent_closings_keep_a_single_consistent_closing_date(postgresql_session_factory) -> None:
    with postgresql_session_factory() as session:
        log_id = store_synthetic_source_log(session).source_log_id
        incident_id = incidents_service.create_incident_from_source_log(session, log_id).id

    def close_incident(start_barrier):
        with postgresql_session_factory() as session:
            start_barrier.wait()
            return incidents_service.change_incident_status(
                session, incident_id, IncidentStatusChangeRequest(statut="cloture")
            )

    closing_outcomes = run_concurrently(close_incident)

    assert all(not isinstance(outcome, Exception) for outcome in closing_outcomes), closing_outcomes
    # Verrou de ligne : les clôtures suivantes voient l'incident déjà clôturé et ne changent pas la date.
    assert len({outcome.closed_at for outcome in closing_outcomes}) == 1
    assert closing_outcomes[0].closed_at >= closing_outcomes[0].created_at
