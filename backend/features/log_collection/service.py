"""Collecte des alertes : un passage = prendre les logs arrivés sur la source, convertir, enregistrer sans doublon, tracer.

En mode réel, FortiAnalyzer transfère ses logs par syslog : un récepteur (démarré avec l'application par
`start_log_reception`) les accumule en mémoire, et chaque collecte vide cette file. En démonstration, la source
invente quelques logs à chaque collecte.

Déroulé de `collect_critical_logs` :
1. période de la collecte : depuis la fin de la dernière collecte réussie (point de reprise), sinon depuis
   `FIRST_COLLECTION_PERIOD` ; jusqu'à maintenant. Elle sert à l'historique et à dater les logs de démonstration ;
2. les logs arrivés sont pris sur la source. Si aucun n'est arrivé et que `is_recorded_when_nothing_received` est
   faux (boucle automatique), rien n'est enregistré : l'historique ne se remplit pas de passages vides toutes les 30 s ;
3. une exécution est inscrite dans l'historique des imports ; chaque log est converti (`fortianalyzer_log_normalizer.py`) ;
   ceux sous la sévérité minimale sont écartés comme par un filtre : ils ne comptent pas dans les « reçus » de
   l'historique (qui doivent tous être enregistrés ou reconnus comme doublons pour une réussite, règle de
   `import_runs`) ; les autres sont enregistrés par `source_logs` (déduplication par identifiant) ;
4. l'exécution est terminée : « réussie », « partielle » (des logs invalides, détaillés dans l'erreur) ou « échouée »
   (réception inactive, base indisponible...). Le point de reprise n'avance que si la collecte n'a pas échoué.

Aucune action n'est jamais envoyée à FortiAnalyzer : l'application ne fait qu'écouter.
Fonctions publiques : `collect_critical_logs_from_configured_source` (source choisie par le .env),
`collect_critical_logs` (source fournie, utilisée par les tests), `describe_collection_configuration`,
`start_log_reception`, `stop_log_reception`.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel, is_at_least_as_severe
from backend.core.settings import ApplicationSettings, get_application_settings
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.schemas import FinishedImportRunStatus, ImportRunFinishedOutcome
from backend.features.log_collection.fortianalyzer_log_normalizer import (
    InvalidFortiAnalyzerLogError,
    normalize_fortianalyzer_log,
)
from backend.features.log_collection.schemas import (
    LogCollectionConfigurationRead,
    LogCollectionResultRead,
    SyslogReceptionStatisticsRead,
)
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import NewSourceLogData
from backend.integrations.fortianalyzer.critical_log_source import CriticalLogSource, RawFortiAnalyzerLog
from backend.integrations.fortianalyzer.demo_log_source import DEMO_SOURCE_DESCRIPTION
from backend.integrations.fortianalyzer.fortianalyzer_errors import FortiAnalyzerError
from backend.integrations.fortianalyzer.log_source_selection import (
    build_critical_log_source,
    build_syslog_reception_parameters,
    list_missing_syslog_settings,
    read_shared_syslog_reception_statistics,
    read_shared_syslog_receiver_startup_error,
    start_shared_syslog_receiver,
    stop_shared_syslog_receiver,
)

log_collection_logger = logging.getLogger(__name__)

# Toute première collecte (aucun point de reprise) : période affichée dans l'historique et utilisée par la démonstration.
FIRST_COLLECTION_PERIOD = timedelta(minutes=5)
# Nombre maximal de motifs d'invalidité recopiés dans l'erreur d'une collecte partielle.
MAXIMUM_INVALID_LOG_REASONS_REPORTED = 5


@dataclass
class LogCollectionCounters:
    """Compteurs d'une collecte en cours."""

    received: int = 0
    inserted: int = 0
    ignored_as_duplicates: int = 0
    below_threshold: int = 0
    invalid_log_reasons: list[str] = field(default_factory=list)

    @property
    def retained(self) -> int:
        """Logs retenus = lus sur la source moins ceux sous le seuil (comptés « reçus » dans l'historique)."""
        return self.received - self.below_threshold


@dataclass(frozen=True)
class CollectionPeriod:
    start: datetime
    end: datetime


class UnavailableLogSource:
    """Source de remplacement quand la source réelle est indisponible : la collecte échoue proprement avec le motif."""

    def __init__(self, unavailability_error: FortiAnalyzerError) -> None:
        self._unavailability_error = unavailability_error

    @property
    def source_description(self) -> str:
        return "Réception syslog (inactive)"

    def take_new_logs(self, period_start: datetime, period_end: datetime) -> list:
        raise self._unavailability_error


def start_log_reception() -> None:
    """Démarre l'écoute syslog en mode réel (au lancement de l'application). Ne lève pas : un échec (port occupé...)
    est journalisé et chaque collecte échoue ensuite avec ce motif, visible dans la page Journaux."""
    start_shared_syslog_receiver(get_application_settings())


def stop_log_reception() -> None:
    """Ferme l'écoute syslog (extinction de l'application)."""
    stop_shared_syslog_receiver()


def collect_critical_logs_from_configured_source(
    database_session: Session, is_recorded_when_nothing_received: bool = True
) -> LogCollectionResultRead | None:
    """Collecte avec la source du .env (démonstration ou réception syslog).

    Retourne None si `is_recorded_when_nothing_received` est faux (boucle automatique) et que rien n'est arrivé ou que
    la source est indisponible. Sinon, une source indisponible (réglage invalide, port non ouvert) donne une
    exécution « échouée » avec le motif, visible dans l'historique des imports.
    """
    settings = get_application_settings()
    try:
        log_source = build_critical_log_source(settings)
    except FortiAnalyzerError as unavailability_error:
        if not is_recorded_when_nothing_received:
            # Boucle automatique : la panne est déjà affichée dans la page Journaux (bandeau) ; l'inscrire toutes les
            # 30 s noierait l'historique. Le bouton « Lancer une collecte » l'inscrit, lui.
            log_collection_logger.warning("Collecte automatique impossible : %s", unavailability_error)
            return None
        log_source = UnavailableLogSource(unavailability_error)
    return collect_critical_logs(
        database_session, log_source, settings, is_recorded_when_nothing_received=is_recorded_when_nothing_received
    )


def collect_critical_logs(
    database_session: Session,
    log_source: CriticalLogSource,
    settings: ApplicationSettings,
    current_time: datetime | None = None,
    is_recorded_when_nothing_received: bool = True,
) -> LogCollectionResultRead | None:
    """Exécute une collecte complète et retourne son bilan (None : rien reçu et rien à enregistrer, voir plus haut).

    Ne lève pas d'exception si la source tombe en panne : la collecte est enregistrée « échouée » (message nettoyé
    de tout secret par `import_runs`) et le bilan l'indique.
    """
    period_end = current_time or datetime.now(UTC)
    period = CollectionPeriod(start=_compute_period_start(database_session, period_end), end=period_end)
    counters = LogCollectionCounters()

    try:
        raw_logs = log_source.take_new_logs(period.start, period.end)
    except Exception as source_error:
        import_run = import_runs_service.start_import_run(database_session)
        return _finish_failed_collection(database_session, import_run.id, log_source, period, counters, source_error)
    if not raw_logs and not is_recorded_when_nothing_received:
        return None

    minimum_criticality = CriticalityLevel(settings.log_collection_minimum_criticality)
    fortianalyzer_timezone = _read_fortianalyzer_timezone(settings)
    import_run = import_runs_service.start_import_run(database_session)
    counters.received = len(raw_logs)
    try:
        for raw_log in raw_logs:
            _store_log_if_severe_enough(
                database_session, raw_log, import_run.id, minimum_criticality, fortianalyzer_timezone, counters
            )
    except Exception as storage_error:
        # Chaque log est validé (commit) dès son enregistrement : les logs déjà enregistrés restent rattachés à
        # l'exécution. Limite assumée : les logs pris sur la file syslog mais pas encore enregistrés sont perdus
        # (FortiAnalyzer les conserve de son côté).
        return _finish_failed_collection(database_session, import_run.id, log_source, period, counters, storage_error)

    if counters.invalid_log_reasons:
        final_status = FinishedImportRunStatus.PARTIALLY_SUCCEEDED
        error_message = (
            f"{len(counters.invalid_log_reasons)} log(s) invalide(s) non enregistré(s) : "
            + " ; ".join(counters.invalid_log_reasons[:MAXIMUM_INVALID_LOG_REASONS_REPORTED])
        )
    else:
        final_status, error_message = FinishedImportRunStatus.SUCCEEDED, None
    return _finish_collection(
        database_session, import_run.id, log_source, period, counters,
        final_status, error_message, synchronization_cursor=period.end.isoformat(),
    )


def describe_collection_configuration(settings: ApplicationSettings) -> LogCollectionConfigurationRead:
    """Décrit la source, la configuration et l'état de la réception syslog (affichage dans l'interface)."""
    common_values = {
        "intervalle_collecte_secondes": settings.log_collection_interval_seconds,
        "severite_minimale": settings.log_collection_minimum_criticality,
    }
    if settings.app_is_in_demo:
        return LogCollectionConfigurationRead(
            est_en_mode_demo=True,
            source=DEMO_SOURCE_DESCRIPTION,
            adresse_ecoute=None,
            port_ecoute=None,
            protocoles=[],
            emetteurs_autorises=[],
            est_a_l_ecoute=False,
            erreur_reception=None,
            reception=None,
            parametres_manquants=[],
            **common_values,
        )
    reception_parameters = build_syslog_reception_parameters(settings)
    protocols = [
        protocol
        for protocol, is_enabled in (
            ("UDP", reception_parameters.is_udp_enabled),
            ("TCP", reception_parameters.is_tcp_enabled),
        )
        if is_enabled
    ]
    reception_statistics = read_shared_syslog_reception_statistics()
    return LogCollectionConfigurationRead(
        est_en_mode_demo=False,
        source=f"Syslog FortiAnalyzer ({'/'.join(protocols) or 'aucun protocole'} port {reception_parameters.listen_port})",
        adresse_ecoute=reception_parameters.listen_address or None,
        port_ecoute=reception_parameters.listen_port,
        protocoles=protocols,
        emetteurs_autorises=sorted(reception_parameters.allowed_sender_addresses),
        est_a_l_ecoute=bool(reception_statistics and reception_statistics.is_listening),
        erreur_reception=read_shared_syslog_receiver_startup_error(),
        reception=(
            SyslogReceptionStatisticsRead(
                nb_logs_en_attente=reception_statistics.pending_log_count,
                nb_messages_acceptes=reception_statistics.accepted_message_count,
                nb_messages_emetteur_refuse=reception_statistics.rejected_sender_message_count,
                nb_messages_illisibles=reception_statistics.unreadable_message_count,
                nb_messages_perdus_file_pleine=reception_statistics.dropped_because_queue_full_count,
            )
            if reception_statistics
            else None
        ),
        parametres_manquants=list_missing_syslog_settings(settings),
        **common_values,
    )


def _store_log_if_severe_enough(
    database_session: Session,
    raw_log: RawFortiAnalyzerLog,
    import_run_id: UUID,
    minimum_criticality: CriticalityLevel,
    fortianalyzer_timezone: ZoneInfo,
    counters: LogCollectionCounters,
) -> None:
    """Convertit et enregistre un log en mettant à jour les compteurs (invalide, sous le seuil, nouveau, doublon)."""
    try:
        normalized_log = normalize_fortianalyzer_log(raw_log, fortianalyzer_timezone)
    except InvalidFortiAnalyzerLogError as invalid_log_error:
        counters.invalid_log_reasons.append(str(invalid_log_error))
        return
    if not is_at_least_as_severe(normalized_log.criticite_source, minimum_criticality):
        counters.below_threshold += 1
        return
    storage_result = source_logs_service.store_source_log_if_new(
        database_session,
        NewSourceLogData(
            identifiant_source=normalized_log.identifiant_source,
            date_evenement=normalized_log.date_evenement,
            type=normalized_log.type,
            criticite_source=normalized_log.criticite_source,
            donnees_brutes=normalized_log.donnees_brutes,
            execution_import_id=import_run_id,
        ),
    )
    if storage_result.was_inserted:
        counters.inserted += 1
    else:
        counters.ignored_as_duplicates += 1


def _compute_period_start(database_session: Session, period_end: datetime) -> datetime:
    synchronization_cursor = import_runs_service.fetch_latest_synchronization_cursor(database_session)
    if synchronization_cursor:
        try:
            return datetime.fromisoformat(synchronization_cursor).astimezone(UTC)
        except ValueError:
            log_collection_logger.warning("Point de reprise illisible : période initiale utilisée.")
    return period_end - FIRST_COLLECTION_PERIOD


def _read_fortianalyzer_timezone(settings: ApplicationSettings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.fortianalyzer_timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _finish_failed_collection(
    database_session: Session,
    import_run_id: UUID,
    log_source: CriticalLogSource,
    period: CollectionPeriod,
    counters: LogCollectionCounters,
    collection_error: Exception,
) -> LogCollectionResultRead:
    # Seule l'éventuelle écriture en cours est annulée ; le point de reprise n'avance pas.
    database_session.rollback()
    log_collection_logger.warning(
        "Collecte échouée (%s) : %s", log_source.source_description, type(collection_error).__name__
    )
    error_message = f"{type(collection_error).__name__}: {collection_error}".strip()
    return _finish_collection(
        database_session, import_run_id, log_source, period, counters,
        FinishedImportRunStatus.FAILED, error_message, synchronization_cursor=None,
    )


def _finish_collection(
    database_session: Session,
    import_run_id: UUID,
    log_source: CriticalLogSource,
    period: CollectionPeriod,
    counters: LogCollectionCounters,
    final_status: FinishedImportRunStatus,
    error_message: str | None,
    synchronization_cursor: str | None,
) -> LogCollectionResultRead:
    finished_import_run = import_runs_service.finish_import_run(
        database_session,
        import_run_id,
        ImportRunFinishedOutcome(
            statut=final_status,
            nb_logs_recus=counters.retained,
            nb_logs_inseres=counters.inserted,
            nb_logs_ignores=counters.ignored_as_duplicates,
            erreur=error_message,
            curseur_synchronisation=synchronization_cursor,
        ),
    )
    return LogCollectionResultRead(
        import_run_id=finished_import_run.id,
        statut=finished_import_run.statut,
        source=log_source.source_description,
        periode_debut=period.start,
        periode_fin=period.end,
        nb_logs_lus_sur_la_source=counters.received,
        nb_logs_recus=counters.retained,
        nb_logs_inseres=counters.inserted,
        nb_logs_ignores=counters.ignored_as_duplicates,
        nb_logs_sous_le_seuil=counters.below_threshold,
        nb_logs_invalides=len(counters.invalid_log_reasons),
        erreur=finished_import_run.erreur,
    )
