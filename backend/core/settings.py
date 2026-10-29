"""Configuration de l'application, lue depuis les variables d'environnement (voir .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://soc:change_me_locally@localhost:5432/soc_incidents"
    application_environment: str = "development"
    log_level: str = "INFO"
    # Origines autorisées pour le futur frontend, séparées par des virgules.
    cors_allowed_origins: str = "http://localhost:8080"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_application_settings() -> ApplicationSettings:
    """Retourne la configuration (lue une seule fois, puis mise en cache)."""
    return ApplicationSettings()
