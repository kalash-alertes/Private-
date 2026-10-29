"""Environnement Alembic : l'URL de la base vient de la configuration de l'application (DATABASE_URL)."""

from alembic import context
from sqlalchemy import create_engine

from backend.core.settings import get_application_settings
from backend.database_model_registry import DatabaseModelBase

target_metadata = DatabaseModelBase.metadata


def run_migrations() -> None:
    database_engine = create_engine(get_application_settings().database_url)
    with database_engine.connect() as database_connection:
        # render_as_batch : les migrations autogénérées restent applicables sur SQLite (tests), qui ne sait pas
        # modifier les contraintes d'une table existante. Sans effet sur PostgreSQL.
        context.configure(connection=database_connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
