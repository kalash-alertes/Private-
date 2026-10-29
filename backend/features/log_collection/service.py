"""Collecte des alertes : un passage = lire une période sur la source, convertir, enregistrer sans doublon, tracer.

Déroulé de `collect_critical_logs` :
1. une exécution « en cours » est ouverte dans l'historique des imports ;
2. période lue : depuis le point de reprise de la dernière collecte réussie (moins un chevauchement de
   `CURSOR_OVERLAP`, pour rattraper les logs indexés en retard par FortiAnalyzer), sinon depuis
   LOG_COLLECTION_INITIAL_LOOKBACK_HOURS ; jusqu'à maintenant ;
3. chaque log est converti (`fortianalyzer_log_normalizer.py`) ; ceux sous la sévérité minimale sont écartés comme
   par un filtre de recherche : ils ne comptent pas dans les « reçus » de l'historique (qui doivent tous être
   enregistrés ou reconnus comme doublons pour une réussite, règle de `import_runs`) ;
   les autres sont enregistrés par `source_logs` (déduplication par identifiant : le chevauchement est sans risque) ;
4. l'exécution est terminée : « réussie », « partielle » (des logs invalides, détaillés dans l'erreur) ou « échouée »
   (source injoignable, identifiants refusés...). Le point de reprise n'avance que si la collecte n'a pas échoué.

Aucune action n'est jamais envoyée à FortiAnalyzer en dehors de la lecture des logs.
Fonctions publiques : `collect_critical_logs_from_configured_source` (source choisie par le .env),
`collect_critical_logs` (source fournie, utilisée par les tests), `describe_collection_configuration`.
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
from backend.features.log_collection.schemas import LogCollectionConfigurationRead, LogCollectionResultRead
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import NewSourceLogData
from backend.integrations.fortianalyzer.critical_log_source import CriticalLogSource
from backend.integrations.fortianalyzer.demo_log_source import DEMO_SOURCE_DESCRIPTION
from backend.integrations.fortianalyzer.fortianalyzer_errors import FortiAnalyzerConfigurationError
from backend.integrations.fortianalyzer.log_source_selection import (
    build_critical_log_source,
    list_missing_fortianalyzer_settings,
)

log_collection_logger = logging.getLogger(__name__)

CURSOR_OVERLAP = timedelta(minutes=10)
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
    """Source de remplacement quand la configuration est invalide : la collecte échoue proprement avec le motif."""

    def __init__(self, configuration_error: FortiAnalyzerConfigurationError) -> None:
        self._configuration_error = configuration_error

    @property
    def source_description(self) -> str:
        return "FortiAnalyzer (configuration incomplète)"

    def fetch_logs_between(self, period_start: datetime, period_end: datetime) -> list:
        raise self._configuration_error


def collect_critical_logs_from_configured_source(database_session: Session) -> LogCollectionResultRead:
    """Collecte avec la source du .env (démonstration ou FortiAnalyzer réel).

    Configuration incomplète en mode réel : la tentative est quand même inscrite (« échouée », avec les variables
    manquantes) pour être visible dans l'historique des imports.
    """
    settings = get_application_settings()
    try:
        log_source = build_critical_log_source(settings)
    except FortiAnalyzerConfigurationError as configuration_error:
        log_source = UnavailableLogSource(configuration_error)
    return collect_critical_logs(database_session, log_source, settings)


def collect_critical_logs(
    database_session: Session,
    log_source: CriticalLogSource,
    settings: ApplicationSettings,
    current_time: datetime | None = None,
) -> LogCollectionResultRead:
    """Exécute une collecte complète et retourne son bilan.

    Ne lève pas d'exception si la source tombe en panne : la collecte est enregistrée « échouée » (message nettoyé
    de tout secret par `import_runs`) et le bilan l'indique.
    """
    period_end = current_time or datetime.now(UTC)
    period = CollectionPeriod(start=_compute_period_start(database_session, settings, period_end), end=period_end)
    minimum_criticality = CriticalityLevel(settings.log_collection_minimum_criticality)
    fortianalyzer_timezone = _read_fortianalyzer_timezone(settings)
    import_run = import_runs_service.start_import_run(database_session)
    counters = LogCollectionCounters()

    try:
        raw_logs = log_source.fetch_logs_between(period.start, period.end)
        counters.received = len(raw_logs)
        for raw_log in raw_logs:
            _store_log_if_severe_enough(
                database_session, raw_log, import_run.id, minimum_criticality, fortianalyzer_timezone, counters
            )
    except Exception as collection_error:
        # Chaque log est validé (commit) dès son enregistrement : les logs déjà enregistrés restent rattachés à
        # l'exécution et ses compteurs les reflètent. Seule l'éventuelle écriture en cours est annulée.
        database_session.rollback()
        log_collection_logger.warning(
            "Collecte échouée (%s) : %s", log_source.source_description, type(collection_error).__name__
        )
        error_message = f"{type(collection_error).__name__}: {collection_error}".strip()
        return _finish_collection(
            database_session, import_run.id, log_source, period, counters,
            FinishedImportRunStatus.FAILED, error_message, synchronization_cursor=None,
        )

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
    """Décrit la source et la configuration de la collecte, sans aucun secret (affichage dans l'interface)."""
    common_values = {
        "intervalle_collecte_secondes": settings.log_collection_interval_seconds,
        "severite_minimale": settings.log_collection_minimum_criticality,
    }
    if settings.app_is_in_demo:
        return LogCollectionConfigurationRead(
            est_en_mode_demo=True,
            source=DEMO_SOURCE_DESCRIPTION,
            adresse_fortianalyzer=None,
            adom=None,
            types_de_logs=[],
            authentification=None,
            parametres_manquants=[],
            **common_values,
        )
    if settings.fortianalyzer_api_token.get_secret_value():
        authentication_description = "Jeton API"
    elif settings.fortianalyzer_username:
        authentication_description = f"Identifiant « {settings.fortianalyzer_username} » + mot de passe"
    else:
        authentication_description = None
    return LogCollectionConfigurationRead(
        est_en_mode_demo=False,
        source=f"FortiAnalyzer {settings.fortianalyzer_base_url or '(adresse non renseignée)'}",
        adresse_fortianalyzer=settings.fortianalyzer_base_url or None,
        adom=settings.fortianalyzer_adom or None,
        types_de_logs=settings.fortianalyzer_log_types_list,
        authentification=authentication_description,
        parametres_manquants=list_missing_fortianalyzer_settings(settings),
        **common_values,
    )


def _store_log_if_severe_enough(
    database_session: Session,
    raw_log: dict,
    import_run_id: UUID,
    minimum_criticality: CriticalityLevel,
    fortianalyzer_timezone: ZoneInfo,
    counters: LogCollectionCounters,
) -> None:
    """Convertit et enregistre un log en mettant à jour les compteurs (invalide, sous le seuil, nouveau, doublon)."""
    try:
        normalized_log = normalize_fortianalyzer_log(raw_log, None, fortianalyzer_timezone)
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


def _compute_period_start(database_session: Session, settings: ApplicationSettings, period_end: datetime) -> datetime:
    synchronization_cursor = import_runs_service.fetch_latest_synchronization_cursor(database_session)
    if synchronization_cursor:
        try:
            return datetime.fromisoformat(synchronization_cursor).astimezone(UTC) - CURSOR_OVERLAP
        except ValueError:
            log_collection_logger.warning("Point de reprise illisible : reprise sur la période initiale.")
    return period_end - timedelta(hours=settings.log_collection_initial_lookback_hours)


def _read_fortianalyzer_timezone(settings: ApplicationSettings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.fortianalyzer_timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


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
