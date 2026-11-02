"""Connexion à la base de données : socle SQLAlchemy partagé par toutes les fonctionnalités."""

from collections.abc import Iterator

from sqlalchemy import JSON, DateTime, MetaData, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.settings import get_application_settings

# Noms de contraintes prévisibles : indispensable pour que les migrations Alembic restent lisibles.
DATABASE_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Toutes les dates sont stockées avec fuseau horaire (TIMESTAMPTZ), en UTC.
TimestampWithTimezoneColumnType = DateTime(timezone=True)

# JSONB sur PostgreSQL ; JSON générique ailleurs (permet de tester sur SQLite).
JsonDocumentColumnType = JSON().with_variant(JSONB(), "postgresql")


class DatabaseModelBase(DeclarativeBase):
    """Classe parente de tous les modèles de tables."""

    metadata = MetaData(naming_convention=DATABASE_NAMING_CONVENTION)


_database_session_factory: sessionmaker[Session] | None = None


def get_database_session_factory() -> sessionmaker[Session]:
    """Crée le moteur et la fabrique de sessions à la première utilisation."""
    global _database_session_factory
    if _database_session_factory is None:
        database_engine = create_engine(get_application_settings().database_url, pool_pre_ping=True)
        _database_session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
    return _database_session_factory


def get_database_session() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, fermée automatiquement."""
    with get_database_session_factory()() as database_session:
        yield database_session
