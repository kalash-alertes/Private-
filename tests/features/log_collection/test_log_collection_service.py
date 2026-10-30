"""Tests de la collecte : enregistrement, doublons, seuil de sévérité, logs invalides, pannes, passages vides, période.

Les sources sont des faux (aucun appel réseau) ; les logs sont synthétiques.
"""

from datetime import UTC, datetime, timedelta

from backend.core.pagination import PaginationParameters
from backend.core.settings import ApplicationSettings
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.models import ImportRunStatus
from backend.features.import_runs.schemas import ImportRunListFilters
from backend.features.log_collection import service as log_collection_service
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import SourceLogListFilters
from backend.integrations.fortianalyzer import log_source_selection
from backend.integrations.fortianalyzer.critical_log_source import SYSLOG_RECEPTION_METADATA_FIELD
from backend.integrations.fortianalyzer.fortianalyzer_errors import SyslogReceptionError

COLLECTION_TIME = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
SYNTHETIC_LOG_TIME = int((COLLECTION_TIME - timedelta(minutes=30)).timestamp())


class FakeLogSource:
    """Source de test : renvoie des logs fixés (ou lève une erreur) et note les périodes demandées."""

    source_description = "Source de test synthétique"

    def __init__(self, logs=None, error: Exception | None = None) -> None:
        self.logs = logs or []
        self.error = error
        self.requested_periods: list[tuple[datetime, datetime]] = []

    def take_new_logs(self, period_start, period_end):
        self.requested_periods.append((period_start, period_end))
        if self.error:
            raise self.error
        return self.logs


def build_settings(**values) -> ApplicationSettings:
    return ApplicationSettings(_env_file=None, **values)


def synthetic_log(level: str = "critical", message: str = "synthétique", subtype: str = "ips") -> dict:
    return {"itime": SYNTHETIC_LOG_TIME, "level": level, "subtype": subtype, "msg": message}


def collect(database_session, log_source, current_time=COLLECTION_TIME, **settings_values):
    return log_collection_service.collect_critical_logs(
        database_session, log_source, build_settings(**settings_values), current_time=current_time
    )


def test_severe_logs_are_stored_once_and_weaker_ones_are_skipped(database_session) -> None:
    log_source = FakeLogSource([synthetic_log("critical", "a"), synthetic_log("error", "b"), synthetic_log("notice", "c")])

    first_result = collect(database_session, log_source)
    second_result = collect(database_session, log_source, current_time=COLLECTION_TIME + timedelta(minutes=5))

    assert first_result.statut == ImportRunStatus.SUCCEEDED
    assert (first_result.nb_logs_lus_sur_la_source, first_result.nb_logs_sous_le_seuil) == (3, 1)
    # Historique : les logs sous le seuil sont écartés comme par un filtre, ils ne comptent pas comme « reçus ».
    assert (first_result.nb_logs_recus, first_result.nb_logs_inseres) == (2, 2)
    # Deuxième passage : mêmes logs (renvoyés par FortiAnalyzer) ⇒ aucun doublon.
    assert (second_result.nb_logs_inseres, second_result.nb_logs_ignores) == (0, 2)
    stored_logs = source_logs_service.list_source_logs(database_session, SourceLogListFilters(), PaginationParameters())
    assert stored_logs.total == 2
    assert {log.type for log in stored_logs.items} == {"ips"}


def test_same_log_received_twice_by_syslog_is_stored_once(database_session) -> None:
    def received_copy(reception_time: str) -> dict:
        return {
            **synthetic_log(),
            SYSLOG_RECEPTION_METADATA_FIELD: {"adresse_emetteur": "192.0.2.104", "recu_le": reception_time},
        }

    result = collect(database_session, FakeLogSource([received_copy("10:00:00"), received_copy("10:00:05")]))

    # L'heure de réception diffère, mais elle est exclue de l'empreinte : le second exemplaire est un doublon.
    assert (result.nb_logs_inseres, result.nb_logs_ignores) == (1, 1)
    stored_log_id = source_logs_service.list_source_logs(
        database_session, SourceLogListFilters(), PaginationParameters()
    ).items[0].id
    stored_log = source_logs_service.fetch_source_log_detail(database_session, stored_log_id)
    assert stored_log.donnees_brutes[SYSLOG_RECEPTION_METADATA_FIELD]["adresse_emetteur"] == "192.0.2.104"


def test_minimum_criticality_is_configurable(database_session) -> None:
    result = collect(
        database_session,
        FakeLogSource([synthetic_log("notice", "a"), synthetic_log("information", "b")]),
        log_collection_minimum_criticality="faible",
    )
    assert (result.nb_logs_inseres, result.nb_logs_sous_le_seuil) == (1, 1)


def test_invalid_logs_make_the_collection_partial(database_session) -> None:
    result = collect(database_session, FakeLogSource([synthetic_log("critical"), {"level": "alert"}]))

    assert result.statut == ImportRunStatus.PARTIALLY_SUCCEEDED
    assert result.nb_logs_inseres == 1 and result.nb_logs_invalides == 1
    assert "Aucune date" in result.erreur


def test_source_failure_is_recorded_and_does_not_advance_the_cursor(database_session) -> None:
    failing_source = FakeLogSource(error=SyslogReceptionError("La réception syslog n'est pas active."))
    first_result = collect(database_session, failing_source)
    retry_source = FakeLogSource([synthetic_log()])
    collect(database_session, retry_source, current_time=COLLECTION_TIME + timedelta(hours=1))

    assert first_result.statut == ImportRunStatus.FAILED
    assert "pas active" in first_result.erreur
    # Après un échec, le point de reprise n'avance pas : la collecte suivante repart de la période initiale.
    retried_period_start, retried_period_end = retry_source.requested_periods[0]
    assert retried_period_end - retried_period_start == log_collection_service.FIRST_COLLECTION_PERIOD


def test_next_collection_starts_where_the_previous_one_ended(database_session) -> None:
    collect(database_session, FakeLogSource([]))
    next_source = FakeLogSource([])
    collect(database_session, next_source, current_time=COLLECTION_TIME + timedelta(minutes=5))

    assert next_source.requested_periods[0] == (COLLECTION_TIME, COLLECTION_TIME + timedelta(minutes=5))


def test_automatic_collection_with_nothing_received_records_nothing(database_session) -> None:
    result = log_collection_service.collect_critical_logs(
        database_session, FakeLogSource([]), build_settings(), COLLECTION_TIME, is_recorded_when_nothing_received=False
    )

    assert result is None
    assert import_runs_service.list_import_runs(
        database_session, ImportRunListFilters(), PaginationParameters()
    ).total == 0


def test_real_mode_without_reception_fails_manually_and_stays_silent_automatically(database_session, monkeypatch) -> None:
    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    monkeypatch.setattr(log_source_selection, "_shared_syslog_receiver", None)
    monkeypatch.setattr(log_source_selection, "_shared_syslog_receiver_startup_error", "port 5140 déjà utilisé")
    from backend.core.settings import get_application_settings

    get_application_settings.cache_clear()
    automatic_result = log_collection_service.collect_critical_logs_from_configured_source(
        database_session, is_recorded_when_nothing_received=False
    )
    manual_result = log_collection_service.collect_critical_logs_from_configured_source(database_session)

    assert automatic_result is None
    assert manual_result.statut == ImportRunStatus.FAILED
    assert "port 5140 déjà utilisé" in manual_result.erreur


def test_configuration_description_in_real_mode() -> None:
    description = log_collection_service.describe_collection_configuration(
        build_settings(app_is_in_demo=False, syslog_is_tcp_enabled=False, syslog_allowed_sender_addresses="192.0.2.104")
    )

    assert description.est_en_mode_demo is False
    assert (description.port_ecoute, description.protocoles) == (5140, ["UDP"])
    assert description.emetteurs_autorises == ["192.0.2.104"]
    assert description.parametres_manquants == []


def test_collection_routes_in_demo_mode(api_client) -> None:
    configuration = api_client.get("/collecte/configuration").json()
    collection_result = api_client.post("/collecte").json()

    assert configuration["est_en_mode_demo"] is True
    assert collection_result["statut"] == "reussie" and collection_result["nb_logs_lus_sur_la_source"] >= 1
    assert api_client.get("/executions-import").json()["total"] == 1


def test_journals_page_shows_the_source_and_runs_a_collection(web_client) -> None:
    page = web_client.get("/journaux").text
    collection_response = web_client.post("/journaux/collecte")

    assert "Mode démonstration" in page and "Lancer une collecte maintenant" in page
    assert collection_response.status_code == 303
    assert "Réussie" in web_client.get("/journaux").text
