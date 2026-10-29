"""Tests du client JSON-RPC FortiAnalyzer contre un faux serveur (aucun appel réseau, identifiants synthétiques)."""

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from backend.integrations.fortianalyzer import fortianalyzer_json_rpc_client
from backend.integrations.fortianalyzer.fortianalyzer_errors import (
    FortiAnalyzerApiError,
    FortiAnalyzerConfigurationError,
    FortiAnalyzerConnectionError,
)
from backend.integrations.fortianalyzer.fortianalyzer_json_rpc_client import (
    FortiAnalyzerConnectionParameters,
    FortiAnalyzerJsonRpcClient,
)
from tests.integrations.fortianalyzer.fake_fortianalyzer_server import (
    FAKE_SESSION_IDENTIFIER,
    FakeFortiAnalyzerServer,
)

SYNTHETIC_PASSWORD = "mot-de-passe-synthetique"
SYNTHETIC_API_TOKEN = "jeton-synthetique"
PERIOD_START = datetime(2026, 10, 29, 8, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def build_parameters(**overrides) -> FortiAnalyzerConnectionParameters:
    values = {
        "base_url": "https://faz.synthetique.test",
        "adom": "root",
        "username": "api.lecture",
        "password": SecretStr(SYNTHETIC_PASSWORD),
        "log_types": ("event",),
        "timezone_name": "Europe/Paris",
    }
    values.update(overrides)
    return FortiAnalyzerConnectionParameters(**values)


def build_client(server: FakeFortiAnalyzerServer, **overrides) -> FortiAnalyzerJsonRpcClient:
    return FortiAnalyzerJsonRpcClient(build_parameters(**overrides), http_transport=server.transport, wait_function=lambda _: None)


def test_password_login_search_pagination_and_logout(monkeypatch) -> None:
    monkeypatch.setattr(fortianalyzer_json_rpc_client, "LOG_SEARCH_PAGE_SIZE", 2)
    synthetic_logs = [{"itime": 1761724800 + index, "level": "critical", "logid": str(index)} for index in range(5)]
    server = FakeFortiAnalyzerServer({"event": synthetic_logs}, searches_in_progress_before_completion=2)

    fetched_logs = build_client(server).fetch_logs_between(PERIOD_START, PERIOD_END)

    assert fetched_logs == synthetic_logs  # 3 pages de 2, après 2 réponses « recherche en cours »
    login_request = server.calls_to("/sys/login/user")[0]
    assert login_request["params"][0]["data"] == {"user": "api.lecture", "passwd": SYNTHETIC_PASSWORD}
    search_request = server.calls_to("/logsearch", "add")[0]
    assert search_request["session"] == FAKE_SESSION_IDENTIFIER
    assert search_request["params"][0]["url"] == "/logview/adom/root/logsearch"
    # Bornes converties dans le fuseau de FortiAnalyzer (Europe/Paris = UTC+1 le 29 octobre 2026).
    assert search_request["params"][0]["time-range"] == {"start": "2026-10-29 09:00:00", "end": "2026-10-29 10:00:00"}
    assert len(server.calls_to("/logsearch/42", "delete")) == 1
    assert len(server.calls_to("/sys/logout")) == 1


def test_api_token_is_sent_as_bearer_header_without_login() -> None:
    server = FakeFortiAnalyzerServer({"attack": [{"itime": 1, "severity": "high"}]})

    build_client(server, api_token=SecretStr(SYNTHETIC_API_TOKEN), log_types=("attack",)).fetch_logs_between(
        PERIOD_START, PERIOD_END
    )

    assert server.calls_to("/sys/login/user") == [] and server.calls_to("/sys/logout") == []
    assert server.received_headers[0]["authorization"] == f"Bearer {SYNTHETIC_API_TOKEN}"
    assert "session" not in server.received_requests[0]


def test_every_configured_log_type_is_searched() -> None:
    server = FakeFortiAnalyzerServer({"event": [{"itime": 1, "level": "alert"}], "attack": [{"itime": 2, "severity": "critical"}]})

    fetched_logs = build_client(server, log_types=("event", "attack")).fetch_logs_between(PERIOD_START, PERIOD_END)

    assert len(fetched_logs) == 2
    assert [call["params"][0]["logtype"] for call in server.calls_to("/logsearch", "add")] == ["event", "attack"]


def test_rejected_login_raises_an_api_error_without_secret() -> None:
    server = FakeFortiAnalyzerServer(login_error_code=-11)

    with pytest.raises(FortiAnalyzerApiError) as raised_error:
        build_client(server).fetch_logs_between(PERIOD_START, PERIOD_END)

    assert "-11" in str(raised_error.value)
    assert SYNTHETIC_PASSWORD not in str(raised_error.value)


def test_http_error_and_unreachable_server_raise_connection_errors() -> None:
    with pytest.raises(FortiAnalyzerConnectionError, match="HTTP 503"):
        build_client(FakeFortiAnalyzerServer(http_status_code=503)).fetch_logs_between(PERIOD_START, PERIOD_END)

    def refuse_connection(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connexion refusée vers https://api.lecture:secret@faz")

    unreachable_client = FortiAnalyzerJsonRpcClient(build_parameters(), http_transport=httpx.MockTransport(refuse_connection))
    with pytest.raises(FortiAnalyzerConnectionError) as raised_error:
        unreachable_client.fetch_logs_between(PERIOD_START, PERIOD_END)
    # Le message d'origine (qui pourrait contenir une URL avec identifiants) n'est pas recopié.
    assert "secret" not in str(raised_error.value) and "ConnectError" in str(raised_error.value)


def test_search_that_never_completes_stops_with_an_error(monkeypatch) -> None:
    monkeypatch.setattr(fortianalyzer_json_rpc_client, "LOG_SEARCH_MAXIMUM_WAIT_SECONDS", 3)
    server = FakeFortiAnalyzerServer({"event": []}, searches_in_progress_before_completion=100)

    with pytest.raises(FortiAnalyzerConnectionError, match="non terminée"):
        build_client(server).fetch_logs_between(PERIOD_START, PERIOD_END)
    assert len(server.calls_to("/sys/logout")) == 1  # déconnexion même en cas d'erreur


def test_unknown_timezone_is_a_configuration_error() -> None:
    with pytest.raises(FortiAnalyzerConfigurationError):
        FortiAnalyzerJsonRpcClient(build_parameters(timezone_name="Fuseau/Inexistant"))


def test_password_never_appears_in_parameters_representation() -> None:
    assert SYNTHETIC_PASSWORD not in repr(build_parameters())
