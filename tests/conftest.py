"""Fixtures communes : base SQLite temporaire migrée par Alembic, sessions et client HTTP de test.

Ces tests valident la logique sur SQLite. Ils ne valident PAS le comportement PostgreSQL (verrous, concurrence réelle,
types natifs) : voir `tests/postgresql_integration/`.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.database import get_database_session
from backend.core.settings import get_application_settings
from backend.main import application

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_sqlite_transactions_reliable(sqlite_engine: Engine) -> None:
    """Corrige la gestion des transactions du pilote Python sqlite3 (recette officielle SQLAlchemy).

    Par défaut, le pilote ouvre les transactions lui-même et casse les SAVEPOINT utilisés par les services ;
    on lui retire ce rôle et SQLAlchemy émet BEGIN explicitement. Active aussi les clés étrangères.
    """

    @event.listens_for(sqlite_engine, "connect")
    def disable_driver_transaction_handling(dbapi_connection, _connection_record) -> None:
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(sqlite_engine, "begin")
    def emit_explicit_begin(connection) -> None:
        connection.exec_driver_sql("BEGIN")


@pytest.fixture
def migrated_sqlite_database_engine(tmp_path, monkeypatch) -> Iterator[Engine]:
    """Base SQLite temporaire créée en appliquant réellement les migrations Alembic."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_application_settings.cache_clear()
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    # check_same_thread=False : le client de test exécute les routes dans un autre thread.
    sqlite_engine = create_engine(database_url, connect_args={"check_same_thread": False})
    make_sqlite_transactions_reliable(sqlite_engine)
    yield sqlite_engine
    sqlite_engine.dispose()
    get_application_settings.cache_clear()


@pytest.fixture
def database_session_factory(migrated_sqlite_database_engine) -> sessionmaker[Session]:
    # Mêmes réglages que la fabrique de l'application (backend/core/database.py).
    return sessionmaker(bind=migrated_sqlite_database_engine, expire_on_commit=False)


@pytest.fixture
def database_session(database_session_factory) -> Iterator[Session]:
    with database_session_factory() as session:
        yield session


@pytest.fixture
def api_client(database_session_factory) -> Iterator[TestClient]:
    """Client HTTP de l'API JSON (préfixe /api) ; chaque requête utilise une session sur la base SQLite de test."""

    def open_test_database_session() -> Iterator[Session]:
        with database_session_factory() as session:
            yield session

    application.dependency_overrides[get_database_session] = open_test_database_session
    # httpx ajoute les chemins relatifs à base_url : `api_client.get("/incidents")` appelle /api/incidents.
    with TestClient(application, base_url="http://testserver/api") as client:
        yield client
    application.dependency_overrides.clear()


@pytest.fixture
def web_client(database_session_factory) -> Iterator[TestClient]:
    """Client HTTP de l'interface web (pages HTML à la racine), sur la base SQLite de test.

    Les redirections ne sont pas suivies automatiquement : les tests vérifient la redirection (303) puis la page.
    """

    def open_test_database_session() -> Iterator[Session]:
        with database_session_factory() as session:
            yield session

    application.dependency_overrides[get_database_session] = open_test_database_session
    with TestClient(application, follow_redirects=False) as client:
        yield client
    application.dependency_overrides.clear()
