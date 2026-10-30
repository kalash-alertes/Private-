"""Choix de la source d'alertes selon la configuration : démonstration (APP_IS_IN_DEMO=true) ou réception syslog réelle.

C'est le SEUL endroit qui lit `app_is_in_demo` pour choisir la source : le reste de l'application reçoit une
`CriticalLogSource` sans savoir laquelle.

La réception syslog est un récepteur PARTAGÉ : démarré une seule fois au lancement de l'application
(`start_shared_syslog_receiver`), il accumule les logs entre deux collectes ; chaque collecte reçoit ce même récepteur.
"""

import logging
import threading

from backend.core.settings import ApplicationSettings
from backend.integrations.fortianalyzer.critical_log_source import CriticalLogSource
from backend.integrations.fortianalyzer.demo_log_source import DemoCriticalLogSource
from backend.integrations.fortianalyzer.fortianalyzer_errors import (
    FortiAnalyzerConfigurationError,
    SyslogReceptionError,
)
from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
    FortiAnalyzerSyslogReceiver,
    SyslogReceptionParameters,
    SyslogReceptionStatistics,
)

log_source_selection_logger = logging.getLogger(__name__)

_shared_syslog_receiver: FortiAnalyzerSyslogReceiver | None = None
# Motif du dernier démarrage raté (port occupé...), recopié dans l'erreur des collectes pour être visible dans Journaux.
_shared_syslog_receiver_startup_error: str | None = None
_shared_syslog_receiver_lock = threading.Lock()


def list_missing_syslog_settings(settings: ApplicationSettings) -> list[str]:
    """Retourne les réglages syslog manquants ou incohérents (liste vide si la réception peut démarrer)."""
    problems = []
    if not settings.syslog_listen_address.strip():
        problems.append("SYSLOG_LISTEN_ADDRESS")
    if not 1 <= settings.syslog_listen_port <= 65_535:
        problems.append("SYSLOG_LISTEN_PORT (entre 1 et 65535)")
    if not (settings.syslog_is_udp_enabled or settings.syslog_is_tcp_enabled):
        problems.append("SYSLOG_IS_UDP_ENABLED ou SYSLOG_IS_TCP_ENABLED (au moins un des deux à true)")
    return problems


def build_syslog_reception_parameters(settings: ApplicationSettings) -> SyslogReceptionParameters:
    """Traduit la configuration en paramètres d'écoute."""
    return SyslogReceptionParameters(
        listen_address=settings.syslog_listen_address.strip(),
        listen_port=settings.syslog_listen_port,
        is_udp_enabled=settings.syslog_is_udp_enabled,
        is_tcp_enabled=settings.syslog_is_tcp_enabled,
        allowed_sender_addresses=frozenset(settings.syslog_allowed_sender_addresses_list),
        maximum_pending_logs=settings.syslog_maximum_pending_logs,
    )


def start_shared_syslog_receiver(settings: ApplicationSettings) -> None:
    """Démarre l'écoute syslog si l'application est en mode réel. Ne lève pas : un échec est journalisé et mémorisé
    (les collectes suivantes échouent avec ce motif, visible dans la page Journaux)."""
    global _shared_syslog_receiver, _shared_syslog_receiver_startup_error
    if settings.app_is_in_demo:
        return
    with _shared_syslog_receiver_lock:
        if _shared_syslog_receiver is not None:
            return
        missing_settings = list_missing_syslog_settings(settings)
        if missing_settings:
            _shared_syslog_receiver_startup_error = "Réglages syslog invalides dans le .env : " + ", ".join(
                missing_settings
            )
            log_source_selection_logger.error(_shared_syslog_receiver_startup_error)
            return
        syslog_receiver = FortiAnalyzerSyslogReceiver(build_syslog_reception_parameters(settings))
        try:
            syslog_receiver.start()
        except SyslogReceptionError as reception_error:
            _shared_syslog_receiver_startup_error = str(reception_error)
            log_source_selection_logger.error("Réception syslog non démarrée : %s", reception_error)
            return
        _shared_syslog_receiver, _shared_syslog_receiver_startup_error = syslog_receiver, None


def stop_shared_syslog_receiver() -> None:
    """Ferme les ports syslog (extinction de l'application). Sans effet si l'écoute n'a pas démarré."""
    global _shared_syslog_receiver
    with _shared_syslog_receiver_lock:
        if _shared_syslog_receiver is not None:
            _shared_syslog_receiver.stop()
            _shared_syslog_receiver = None


def read_shared_syslog_reception_statistics() -> SyslogReceptionStatistics | None:
    """Compteurs de la réception partagée, ou None si elle n'a pas démarré."""
    syslog_receiver = _shared_syslog_receiver
    return syslog_receiver.read_reception_statistics() if syslog_receiver is not None else None


def read_shared_syslog_receiver_startup_error() -> str | None:
    """Motif du dernier démarrage raté de la réception syslog, ou None."""
    return _shared_syslog_receiver_startup_error


def build_critical_log_source(settings: ApplicationSettings) -> CriticalLogSource:
    """Retourne la source à utiliser.

    Lève FortiAnalyzerConfigurationError si le mode réel est mal configuré, SyslogReceptionError si la réception
    syslog n'a pas démarré (motif du démarrage raté repris dans le message).
    """
    if settings.app_is_in_demo:
        return DemoCriticalLogSource()
    missing_settings = list_missing_syslog_settings(settings)
    if missing_settings:
        raise FortiAnalyzerConfigurationError(
            "APP_IS_IN_DEMO=false mais la réception syslog est mal configurée dans le .env : "
            + ", ".join(missing_settings)
        )
    if _shared_syslog_receiver is None:
        raise SyslogReceptionError(
            "La réception syslog n'est pas active"
            + (f" : {_shared_syslog_receiver_startup_error}" if _shared_syslog_receiver_startup_error else ".")
        )
    return _shared_syslog_receiver
