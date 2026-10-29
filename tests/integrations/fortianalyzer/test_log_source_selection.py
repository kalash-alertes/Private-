"""Tests du choix de la source (APP_IS_IN_DEMO) et de la source de démonstration."""

import random
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from backend.core.settings import ApplicationSettings
from backend.integrations.fortianalyzer.demo_log_source import DemoCriticalLogSource
from backend.integrations.fortianalyzer.fortianalyzer_errors import FortiAnalyzerConfigurationError
from backend.integrations.fortianalyzer.fortianalyzer_json_rpc_client import FortiAnalyzerJsonRpcClient
from backend.integrations.fortianalyzer.log_source_selection import (
    build_connection_parameters,
    build_critical_log_source,
    list_missing_fortianalyzer_settings,
)


def build_settings(**values) -> ApplicationSettings:
    # _env_file=None : le .env du poste n'influence pas le test.
    return ApplicationSettings(_env_file=None, **values)


def test_demo_mode_uses_the_demo_source_even_without_connection_settings() -> None:
    assert isinstance(build_critical_log_source(build_settings(app_is_in_demo=True)), DemoCriticalLogSource)


def test_real_mode_lists_missing_settings() -> None:
    settings = build_settings(app_is_in_demo=False)

    assert list_missing_fortianalyzer_settings(settings) == [
        "FORTIANALYZER_BASE_URL",
        "FORTIANALYZER_USERNAME (ou FORTIANALYZER_API_TOKEN)",
        "FORTIANALYZER_PASSWORD (ou FORTIANALYZER_API_TOKEN)",
    ]
    with pytest.raises(FortiAnalyzerConfigurationError, match="FORTIANALYZER_BASE_URL"):
        build_critical_log_source(settings)


def test_real_mode_with_token_or_password_builds_the_real_client() -> None:
    with_token = build_settings(
        app_is_in_demo=False, fortianalyzer_base_url="https://faz.synthetique.test/", fortianalyzer_api_token="jeton"
    )
    with_password = build_settings(
        app_is_in_demo=False,
        fortianalyzer_base_url="https://faz.synthetique.test",
        fortianalyzer_username="api.lecture",
        fortianalyzer_password="mot-de-passe",
    )

    assert isinstance(build_critical_log_source(with_token), FortiAnalyzerJsonRpcClient)
    assert isinstance(build_critical_log_source(with_password), FortiAnalyzerJsonRpcClient)
    assert build_connection_parameters(with_token).base_url == "https://faz.synthetique.test"


def test_ca_bundle_path_takes_precedence_over_tls_flag() -> None:
    settings = build_settings(fortianalyzer_verify_tls=False, fortianalyzer_ca_bundle_path="/application/certificates/ca.pem")
    assert build_connection_parameters(settings).tls_verification == "/application/certificates/ca.pem"
    assert build_connection_parameters(build_settings(fortianalyzer_verify_tls=False)).tls_verification is False


def test_secrets_are_hidden_and_unknown_minimum_criticality_is_refused() -> None:
    settings = build_settings(fortianalyzer_password="mot-de-passe", fortianalyzer_api_token=SecretStr("jeton"))
    assert "mot-de-passe" not in repr(settings) and "jeton" not in str(settings)
    with pytest.raises(ValueError):
        build_settings(log_collection_minimum_criticality="extreme")


def test_demo_source_returns_marked_logs_inside_the_period() -> None:
    period_end = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    period_start = period_end - timedelta(hours=1)

    demo_logs = DemoCriticalLogSource(random.Random(7)).fetch_logs_between(period_start, period_end)

    assert 1 <= len(demo_logs) <= 4
    assert all(log["demonstration"] is True and log["devid"].startswith("DEMO-") for log in demo_logs)
    assert all(period_start.timestamp() <= log["itime"] <= period_end.timestamp() for log in demo_logs)
