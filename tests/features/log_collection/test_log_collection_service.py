"""Tests de la collecte : enregistrement, doublons, seuil de sévérité, logs invalides, pannes, point de reprise.

Les sources sont des faux (aucun appel réseau) ; les logs sont synthétiques.
"""

from datetime import UTC, datetime, timedelta

from backend.core.pagination import PaginationParameters
from backend.core.settings import ApplicationSettings
from backend.features.import_runs.models import ImportRunStatus
from backend.features.log_collection import service as log_collection_service
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import SourceLogListFilters
from backend.integrations.fortianalyzer.fortianalyzer_errors import FortiAnalyzerApiError

COLLECTION_TIME = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
SYNTHETIC_LOG_TIME = int((COLLECTION_TIME - timedelta(minutes=30)).timestamp())


class FakeLogSource:
    """Source de test : renvoie des logs fixés (ou lève une erreur) et note les périodes demandées."""

    source_description = "Source de test synthétique"

    def __init__(self, logs=None, error: Exception | None = None) -> None:
        self.logs = logs or []
        self.error = error
        self.requested_periods: list[tuple[datetime, datetime]] = []

    def fetch_logs_between(self, period_start, period_end):
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
    # Deuxième passage : mêmes logs (périodes qui se chevauchent) ⇒ aucun doublon.
    assert (second_result.nb_logs_inseres, second_result.nb_logs_ignores) == (0, 2)
    stored_logs = source_logs_service.list_source_logs(database_session, SourceLogListFilters(), PaginationParameters())
    assert stored_logs.total == 2
    assert {log.type for log in stored_logs.items} == {"ips"}


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


def test_source_failure_is_recorded_without_secret_and_does_not_advance_the_cursor(database_session) -> None:
    failing_source = FakeLogSource(error=FortiAnalyzerApiError("connexion : erreur FortiAnalyzer -11 password=secret"))
    first_result = collect(database_session, failing_source)
    retry_source = FakeLogSource([synthetic_log()])
    collect(database_session, retry_source, current_time=COLLECTION_TIME + timedelta(hours=1))

    assert first_result.statut == ImportRunStatus.FAILED
    assert "-11" in first_result.erreur and "secret" not in first_result.erreur
    # Après un échec, le point de reprise n'avance pas : la collecte suivante relit la période initiale (24 h).
    retried_period_start, retried_period_end = retry_source.requested_periods[0]
    assert retried_period_end - retried_period_start == timedelta(hours=24)


def test_next_collection_resumes_from_the_cursor_with_an_overlap(database_session) -> None:
    collect(database_session, FakeLogSource([]))
    next_source = FakeLogSource([])
    collect(database_session, next_source, current_time=COLLECTION_TIME + timedelta(minutes=5))

    period_start, period_end = next_source.requested_periods[0]
    assert period_start == COLLECTION_TIME - log_collection_service.CURSOR_OVERLAP
    assert period_end == COLLECTION_TIME + timedelta(minutes=5)


def test_incomplete_real_configuration_is_recorded_as_a_failed_collection(database_session, monkeypatch) -> None:
    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    monkeypatch.setenv("FORTIANALYZER_BASE_URL", "")
    from backend.core.settings import get_application_settings

    get_application_settings.cache_clear()
    result = log_collection_service.collect_critical_logs_from_configured_source(database_session)

    assert result.statut == ImportRunStatus.FAILED
    assert "FORTIANALYZER_BASE_URL" in result.erreur


def test_configuration_description_never_contains_secrets() -> None:
    description = log_collection_service.describe_collection_configuration(
        build_settings(
            app_is_in_demo=False,
            fortianalyzer_base_url="https://faz.synthetique.test",
            fortianalyzer_username="api.lecture",
            fortianalyzer_password="mot-de-passe-synthetique",
        )
    )

    assert "mot-de-passe-synthetique" not in description.model_dump_json()
    assert description.parametres_manquants == []
    assert description.authentification == "Identifiant « api.lecture » + mot de passe"


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
