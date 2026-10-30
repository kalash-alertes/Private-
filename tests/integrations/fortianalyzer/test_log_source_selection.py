"""Tests du choix de la source (APP_IS_IN_DEMO), du récepteur syslog partagé et de la source de démonstration."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from backend.core.settings import ApplicationSettings
from backend.integrations.fortianalyzer import log_source_selection
from backend.integrations.fortianalyzer.demo_log_source import DemoCriticalLogSource
from backend.integrations.fortianalyzer.fortianalyzer_errors import (
    FortiAnalyzerConfigurationError,
    SyslogReceptionError,
)
from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import FortiAnalyzerSyslogReceiver
from backend.integrations.fortianalyzer.log_source_selection import (
    build_critical_log_source,
    build_syslog_reception_parameters,
    list_missing_syslog_settings,
)


def build_settings(**values) -> ApplicationSettings:
    # _env_file=None : le .env du poste n'influence pas le test.
    return ApplicationSettings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def reset_shared_syslog_receiver():
    """Chaque test part d'un récepteur partagé arrêté, et le referme à la fin (aucun port laissé ouvert)."""
    log_source_selection.stop_shared_syslog_receiver()
    log_source_selection._shared_syslog_receiver_startup_error = None
    yield
    log_source_selection.stop_shared_syslog_receiver()
    log_source_selection._shared_syslog_receiver_startup_error = None


def test_demo_mode_uses_the_demo_source_and_never_opens_a_port() -> None:
    settings = build_settings(app_is_in_demo=True)
    log_source_selection.start_shared_syslog_receiver(settings)

    assert isinstance(build_critical_log_source(settings), DemoCriticalLogSource)
    assert log_source_selection.read_shared_syslog_reception_statistics() is None


def test_invalid_syslog_settings_are_listed_and_refused() -> None:
    settings = build_settings(
        app_is_in_demo=False, syslog_listen_port=0, syslog_is_udp_enabled=False, syslog_is_tcp_enabled=False
    )

    assert list_missing_syslog_settings(settings) == [
        "SYSLOG_LISTEN_PORT (entre 1 et 65535)",
        "SYSLOG_IS_UDP_ENABLED ou SYSLOG_IS_TCP_ENABLED (au moins un des deux à true)",
    ]
    with pytest.raises(FortiAnalyzerConfigurationError, match="SYSLOG_LISTEN_PORT"):
        build_critical_log_source(settings)


def test_real_mode_without_started_reception_reports_the_startup_error() -> None:
    log_source_selection._shared_syslog_receiver_startup_error = "Impossible d'écouter sur 0.0.0.0:5140"

    with pytest.raises(SyslogReceptionError, match="Impossible d'écouter"):
        build_critical_log_source(build_settings(app_is_in_demo=False))


def test_real_mode_returns_the_shared_receiver_once_started(monkeypatch) -> None:
    # Pas de vrai port : on remplace l'ouverture des sockets par un démarrage factice.
    monkeypatch.setattr(FortiAnalyzerSyslogReceiver, "start", lambda receiver: None)
    settings = build_settings(app_is_in_demo=False)
    log_source_selection.start_shared_syslog_receiver(settings)

    first_source, second_source = build_critical_log_source(settings), build_critical_log_source(settings)

    assert isinstance(first_source, FortiAnalyzerSyslogReceiver) and first_source is second_source


def test_reception_parameters_come_from_settings() -> None:
    parameters = build_syslog_reception_parameters(
        build_settings(syslog_listen_port=6514, syslog_allowed_sender_addresses=" 192.0.2.10, 192.0.2.11 ,")
    )

    assert parameters.listen_port == 6514
    assert parameters.allowed_sender_addresses == frozenset({"192.0.2.10", "192.0.2.11"})


def test_unknown_minimum_criticality_is_refused() -> None:
    with pytest.raises(ValueError):
        build_settings(log_collection_minimum_criticality="extreme")


def test_demo_source_returns_marked_logs_inside_the_period() -> None:
    period_end = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    period_start = period_end - timedelta(hours=1)

    demo_logs = DemoCriticalLogSource(random.Random(7)).take_new_logs(period_start, period_end)

    assert 1 <= len(demo_logs) <= 4
    assert all(log["demonstration"] is True and log["devid"].startswith("DEMO-") for log in demo_logs)
    assert all(period_start.timestamp() <= log["itime"] <= period_end.timestamp() for log in demo_logs)
