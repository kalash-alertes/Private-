"""Vérifie le schéma de base : migrations alignées sur les modèles, et contraintes métier appliquées.

Les tests tournent sur SQLite (pas de Docker requis). Les types propres à PostgreSQL ont un équivalent générique.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.settings import get_application_settings
from backend.database_model_registry import DatabaseModelBase, ImportRun, Incident, SourceLog

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def migrated_database_engine(tmp_path, monkeypatch):
    """Base SQLite temporaire créée en appliquant réellement les migrations Alembic."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_application_settings.cache_clear()
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    engine = create_engine(database_url)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    yield engine
    engine.dispose()
    get_application_settings.cache_clear()


def _create_import_run_and_log(session: Session) -> SourceLog:
    import_run = ImportRun(statut="reussie", fin=datetime.now(UTC))
    session.add(import_run)
    session.flush()
    source_log = SourceLog(
        identifiant_source="fortianalyzer-event-1",
        date_evenement=datetime.now(UTC),
        type="intrusion",
        criticite_source="critique",
        execution_import_id=import_run.id,
    )
    session.add(source_log)
    session.flush()
    return source_log


def test_migrations_match_the_sqlalchemy_models(migrated_database_engine) -> None:
    with migrated_database_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), DatabaseModelBase.metadata)

    assert differences == []


def test_same_source_identifier_cannot_be_stored_twice(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        first_log = _create_import_run_and_log(session)
        session.add(
            SourceLog(
                identifiant_source=first_log.identifiant_source,
                date_evenement=datetime.now(UTC),
                type="intrusion",
                criticite_source="critique",
                execution_import_id=first_log.execution_import_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_false_positive_incident_requires_a_justification(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        session.add(Incident(log_id=source_log.id, criticite_actuelle="critique", faux_positif=True))
        with pytest.raises(IntegrityError):
            session.flush()


def test_closed_incident_requires_a_closing_date(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        session.add(Incident(log_id=source_log.id, criticite_actuelle="critique", statut="cloture"))
        with pytest.raises(IntegrityError):
            session.flush()


def test_a_log_can_have_only_one_incident(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        session.add(Incident(log_id=source_log.id, criticite_actuelle="critique"))
        session.flush()
        session.add(Incident(log_id=source_log.id, criticite_actuelle="haute"))
        with pytest.raises(IntegrityError):
            session.flush()


# --- Contraintes ajoutées par la migration 0002 ---


@pytest.mark.parametrize(
    "import_run_values",
    [
        pytest.param({"statut": "reussie", "nb_logs_recus": 1, "nb_logs_inseres": 1, "nb_logs_ignores": 1}, id="compteurs"),
        pytest.param({"statut": "echouee", "erreur": None}, id="echec_sans_erreur"),
        pytest.param({"statut": "partielle", "erreur": ""}, id="partielle_erreur_vide"),
        pytest.param({"statut": "reussie", "erreur": "inattendu"}, id="reussite_avec_erreur"),
        pytest.param(
            {"statut": "reussie", "debut": datetime(2026, 10, 2, tzinfo=UTC), "fin": datetime(2026, 10, 1, tzinfo=UTC)},
            id="fin_avant_debut",
        ),
    ],
)
def test_inconsistent_import_run_is_rejected_by_the_database(migrated_database_engine, import_run_values) -> None:
    with Session(migrated_database_engine) as session:
        import_run_values.setdefault("fin", datetime.now(UTC))
        session.add(ImportRun(**import_run_values))
        with pytest.raises(IntegrityError):
            session.flush()


def test_blank_source_identifier_is_rejected_by_the_database(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        source_log.identifiant_source = ""
        with pytest.raises(IntegrityError):
            session.flush()


def test_blank_assignee_is_rejected_by_the_database(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        session.add(Incident(log_id=source_log.id, criticite_actuelle="critique", assigne_a=""))
        with pytest.raises(IntegrityError):
            session.flush()


def test_incident_cannot_be_closed_before_its_creation(migrated_database_engine) -> None:
    with Session(migrated_database_engine) as session:
        source_log = _create_import_run_and_log(session)
        session.add(
            Incident(
                log_id=source_log.id,
                criticite_actuelle="critique",
                statut="cloture",
                created_at=datetime(2026, 10, 2, tzinfo=UTC),
                closed_at=datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_migrations_can_be_rolled_back_and_reapplied(migrated_database_engine) -> None:
    alembic_configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.downgrade(alembic_configuration, "base")
    command.upgrade(alembic_configuration, "head")

    with migrated_database_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), DatabaseModelBase.metadata)
    assert differences == []
