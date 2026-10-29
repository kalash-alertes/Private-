"""Choix de la source d'alertes selon la configuration : démonstration (APP_IS_IN_DEMO=true) ou FortiAnalyzer réel.

C'est le SEUL endroit qui lit `app_is_in_demo` pour choisir la source : le reste de l'application reçoit une
`CriticalLogSource` sans savoir laquelle.
"""

from backend.core.settings import ApplicationSettings
from backend.integrations.fortianalyzer.critical_log_source import CriticalLogSource
from backend.integrations.fortianalyzer.demo_log_source import DemoCriticalLogSource
from backend.integrations.fortianalyzer.fortianalyzer_errors import FortiAnalyzerConfigurationError
from backend.integrations.fortianalyzer.fortianalyzer_json_rpc_client import (
    FortiAnalyzerConnectionParameters,
    FortiAnalyzerJsonRpcClient,
)


def list_missing_fortianalyzer_settings(settings: ApplicationSettings) -> list[str]:
    """Retourne les variables du .env manquantes pour se connecter (liste vide si tout est renseigné)."""
    missing_settings = []
    if not settings.fortianalyzer_base_url.strip():
        missing_settings.append("FORTIANALYZER_BASE_URL")
    has_api_token = bool(settings.fortianalyzer_api_token.get_secret_value())
    if not has_api_token:
        if not settings.fortianalyzer_username.strip():
            missing_settings.append("FORTIANALYZER_USERNAME (ou FORTIANALYZER_API_TOKEN)")
        if not settings.fortianalyzer_password.get_secret_value():
            missing_settings.append("FORTIANALYZER_PASSWORD (ou FORTIANALYZER_API_TOKEN)")
    if not settings.fortianalyzer_adom.strip():
        missing_settings.append("FORTIANALYZER_ADOM")
    if not settings.fortianalyzer_log_types_list:
        missing_settings.append("FORTIANALYZER_LOG_TYPES")
    return missing_settings


def build_critical_log_source(settings: ApplicationSettings) -> CriticalLogSource:
    """Retourne la source à utiliser. Lève FortiAnalyzerConfigurationError si le mode réel est mal configuré."""
    if settings.app_is_in_demo:
        return DemoCriticalLogSource()
    missing_settings = list_missing_fortianalyzer_settings(settings)
    if missing_settings:
        raise FortiAnalyzerConfigurationError(
            "APP_IS_IN_DEMO=false mais la connexion FortiAnalyzer est incomplète dans le .env : "
            + ", ".join(missing_settings)
        )
    return FortiAnalyzerJsonRpcClient(build_connection_parameters(settings))


def build_connection_parameters(settings: ApplicationSettings) -> FortiAnalyzerConnectionParameters:
    """Traduit la configuration en paramètres de connexion (un fichier CA, s'il est indiqué, prime sur true/false)."""
    return FortiAnalyzerConnectionParameters(
        base_url=settings.fortianalyzer_base_url.strip().rstrip("/"),
        adom=settings.fortianalyzer_adom.strip(),
        api_token=settings.fortianalyzer_api_token,
        username=settings.fortianalyzer_username.strip(),
        password=settings.fortianalyzer_password,
        tls_verification=settings.fortianalyzer_ca_bundle_path.strip() or settings.fortianalyzer_verify_tls,
        log_types=tuple(settings.fortianalyzer_log_types_list),
        device_identifier=settings.fortianalyzer_device_identifier.strip() or "All_FortiGate",
        search_filter=settings.fortianalyzer_search_filter.strip(),
        timezone_name=settings.fortianalyzer_timezone.strip() or "UTC",
        request_timeout_seconds=settings.fortianalyzer_request_timeout_seconds,
    )
