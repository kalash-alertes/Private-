"""Fixtures des tests d'intégration sur un VRAI PostgreSQL.

Activation : définir `TEST_POSTGRESQL_DATABASE_URL` vers une base DÉDIÉE aux tests (son nom doit contenir « test »),
par exemple `postgresql+psycopg://soc:change_me_locally@localhost:5432/soc_incidents_test`.
Sans cette variable, ces tests sont ignorés (marqués « skipped ») : ils ne sont alors PAS validés.

ATTENTION : la base est entièrement vidée (migrations annulées puis réappliquées). Ne jamais pointer vers une base utile.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from backend.core.settings import get_application_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_POSTGRESQL_DATABASE_URL_VARIABLE = "TEST_POSTGRESQL_DATABASE_URL"

pytestmark = pytest.mark.postgresql


def read_test_postgresql_database_url() -> str:
    """Retourne l'URL de la base PostgreSQL de test, ou ignore les tests si elle n'est pas fournie ou non dédiée."""
    database_url = os.environ.get(TEST_POSTGRESQL_DATABASE_URL_VARIABLE)
    if not database_url:
        pytest.skip(f"{TEST_POSTGRESQL_DATABASE_URL_VARIABLE} non défini : tests PostgreSQL non exécutés")
    parsed_database_url = make_url(database_url)
    if not parsed_database_url.drivername.startswith("postgresql"):
        pytest.fail(f"{TEST_POSTGRESQL_DATABASE_URL_VARIABLE} doit désigner une base PostgreSQL")
    if "test" not in (parsed_database_url.database or ""):
        # Garde-fou : ces tests détruisent le schéma.
        pytest.fail("Le nom de la base PostgreSQL de test doit contenir « test » (la base est vidée par les tests)")
    return database_url


@pytest.fixture(scope="session")
def migrated_postgresql_database_engine() -> Iterator[Engine]:
    """Base PostgreSQL remise à zéro puis migrée jusqu'à la dernière version (une fois pour la session de tests)."""
    database_url = read_test_postgresql_database_url()
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_application_settings.cache_clear()
    alembic_configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.downgrade(alembic_configuration, "base")
    command.upgrade(alembic_configuration, "head")
    postgresql_engine = create_engine(database_url, pool_size=10)
    yield postgresql_engine
    postgresql_engine.dispose()
    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url
    get_application_settings.cache_clear()


@pytest.fixture
def postgresql_session_factory(migrated_postgresql_database_engine) -> Iterator[sessionmaker[Session]]:
    """Fabrique de sessions sur une base vidée de ses données avant chaque test."""
    with migrated_postgresql_database_engine.begin() as connection:
        connection.execute(text("TRUNCATE incidents, logs, executions_import"))
    yield sessionmaker(bind=migrated_postgresql_database_engine, expire_on_commit=False)
