"""Configuration de l'application, lue depuis les variables d'environnement (voir .env.example).

La réception des logs ne demande aucun secret : FortiAnalyzer les envoie par syslog sur un port d'écoute.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.criticality import CriticalityLevel


class ApplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://soc:change_me_locally@localhost:5432/soc_incidents"
    application_environment: str = "development"
    log_level: str = "INFO"
    # Origines autorisées pour un éventuel client externe de l'API, séparées par des virgules.
    cors_allowed_origins: str = "http://localhost:8080"
    # Intervalle de l'escalade automatique des incidents en retard, en secondes. 0 = boucle désactivée
    # (l'escalade reste déclenchable par POST /api/incidents/escalade-automatique).
    automatic_escalation_interval_seconds: float = 0

    # --- Source des alertes ---
    # true : alertes de DÉMONSTRATION inventées (aucun port syslog ouvert).
    # false : alertes réelles, transférées par FortiAnalyzer en syslog sur le port décrit ci-dessous.
    app_is_in_demo: bool = True

    # --- Collecte des alertes ---
    # Intervalle de la collecte automatique, en secondes : vide la file des logs reçus par syslog et les enregistre.
    # 0 = boucle désactivée (collecte manuelle uniquement ; en mode réel, les logs s'accumulent alors en mémoire).
    log_collection_interval_seconds: float = 0
    # Sévérité minimale enregistrée (information, faible, moyenne, haute, critique) : seuls les logs critiques
    # intéressent l'application (cadrage) ; les autres sont lus mais pas enregistrés.
    log_collection_minimum_criticality: str = "haute"

    # --- Réception syslog (utilisée seulement si app_is_in_demo = false) ---
    syslog_listen_address: str = "0.0.0.0"
    # 514 est le port standard mais demande des droits administrateur ; 5140 n'en demande pas.
    syslog_listen_port: int = 5140
    syslog_is_udp_enabled: bool = True
    syslog_is_tcp_enabled: bool = True
    # Adresses IP autorisées à envoyer des logs, séparées par des virgules (vide = toutes). Le syslog n'est pas
    # authentifié : renseigner l'adresse de FortiAnalyzer évite qu'une autre machine injecte de faux logs.
    syslog_allowed_sender_addresses: str = ""
    # Nombre maximal de logs en attente de collecte (au-delà, les messages sont perdus et comptés).
    syslog_maximum_pending_logs: int = 100_000
    # Fuseau des champs `date` + `time` d'un log, quand il n'a ni `eventtime`, ni `itime`, ni `tz`.
    fortianalyzer_timezone: str = "UTC"

    @field_validator("log_collection_minimum_criticality")
    @classmethod
    def check_minimum_criticality_is_known(cls, minimum_criticality: str) -> str:
        """Refuse au démarrage une sévérité inconnue (faute de frappe dans le .env) plutôt qu'à la première collecte."""
        return CriticalityLevel(minimum_criticality.strip().lower()).value

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def syslog_allowed_sender_addresses_list(self) -> list[str]:
        return [address.strip() for address in self.syslog_allowed_sender_addresses.split(",") if address.strip()]


@lru_cache
def get_application_settings() -> ApplicationSettings:
    """Retourne la configuration (lue une seule fois, puis mise en cache)."""
    return ApplicationSettings()
