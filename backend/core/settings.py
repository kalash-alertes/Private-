"""Configuration de l'application, lue depuis les variables d'environnement (voir .env.example).

Les secrets (mot de passe et jeton FortiAnalyzer) sont des `SecretStr` : ils ne s'affichent jamais en clair dans un
`print`, un log ou un message d'erreur (`**********`). Leur valeur n'est lue qu'au moment de l'appel réseau.
"""

from functools import lru_cache

from pydantic import SecretStr, field_validator
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
    # true : alertes de DÉMONSTRATION inventées (aucune connexion à FortiAnalyzer).
    # false : alertes réelles lues sur le FortiAnalyzer décrit ci-dessous.
    app_is_in_demo: bool = True

    # --- Collecte des alertes ---
    # Intervalle de la collecte automatique, en secondes. 0 = boucle désactivée (collecte manuelle uniquement).
    log_collection_interval_seconds: float = 0
    # Première collecte (aucune collecte réussie auparavant) : nombre d'heures d'historique à récupérer.
    log_collection_initial_lookback_hours: float = 24
    # Sévérité minimale enregistrée (information, faible, moyenne, haute, critique) : seuls les logs critiques
    # intéressent l'application (cadrage) ; les autres sont comptés comme « reçus » mais pas enregistrés.
    log_collection_minimum_criticality: str = "haute"

    # --- Connexion FortiAnalyzer (utilisée seulement si app_is_in_demo = false) ---
    fortianalyzer_base_url: str = ""
    # Authentification : jeton API (FortiAnalyzer 7.2.2 et plus, recommandé) OU identifiant + mot de passe.
    fortianalyzer_api_token: SecretStr = SecretStr("")
    fortianalyzer_username: str = ""
    fortianalyzer_password: SecretStr = SecretStr("")
    fortianalyzer_adom: str = "root"
    # Vérification du certificat HTTPS. Préférer un fichier d'autorité (CA) à la désactivation.
    fortianalyzer_verify_tls: bool = True
    fortianalyzer_ca_bundle_path: str = ""
    # Types de logs interrogés, séparés par des virgules (ex. event, attack, virus, traffic).
    fortianalyzer_log_types: str = "event,attack"
    # Équipements interrogés : identifiant FortiAnalyzer (All_FortiGate = tous les FortiGate de l'ADOM).
    fortianalyzer_device_identifier: str = "All_FortiGate"
    # Filtre de recherche facultatif, dans la syntaxe de FortiAnalyzer (laissé vide : filtrage par sévérité côté app).
    fortianalyzer_search_filter: str = ""
    # Fuseau horaire dans lequel FortiAnalyzer interprète les bornes de recherche.
    fortianalyzer_timezone: str = "UTC"
    fortianalyzer_request_timeout_seconds: float = 30

    @field_validator("log_collection_minimum_criticality")
    @classmethod
    def check_minimum_criticality_is_known(cls, minimum_criticality: str) -> str:
        """Refuse au démarrage une sévérité inconnue (faute de frappe dans le .env) plutôt qu'à la première collecte."""
        return CriticalityLevel(minimum_criticality.strip().lower()).value

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def fortianalyzer_log_types_list(self) -> list[str]:
        return [log_type.strip() for log_type in self.fortianalyzer_log_types.split(",") if log_type.strip()]


@lru_cache
def get_application_settings() -> ApplicationSettings:
    """Retourne la configuration (lue une seule fois, puis mise en cache)."""
    return ApplicationSettings()
