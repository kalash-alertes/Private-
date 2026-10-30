"""Tests de la conversion d'un log FortiAnalyzer (logs synthétiques au format FortiAnalyzer)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from backend.core.criticality import CriticalityLevel
from backend.features.log_collection.fortianalyzer_log_normalizer import (
    InvalidFortiAnalyzerLogError,
    compute_source_identifier,
    normalize_fortianalyzer_log,
)
from backend.integrations.fortianalyzer.critical_log_source import SYSLOG_RECEPTION_METADATA_FIELD

PARIS_TIMEZONE = ZoneInfo("Europe/Paris")


def normalize(raw_log):
    return normalize_fortianalyzer_log(raw_log, PARIS_TIMEZONE)


@pytest.mark.parametrize(
    ("severity_fields", "expected_criticality"),
    [
        ({"level": "emergency"}, CriticalityLevel.CRITICAL),
        ({"level": "alert"}, CriticalityLevel.CRITICAL),
        ({"level": "error"}, CriticalityLevel.HIGH),
        ({"level": "warning"}, CriticalityLevel.MEDIUM),
        ({"level": "notice"}, CriticalityLevel.LOW),
        ({"level": "information"}, CriticalityLevel.INFORMATION),
        ({"severity": "High"}, CriticalityLevel.HIGH),
        # `severity` (logs d'attaque) prime sur `level`.
        ({"severity": "critical", "level": "notice"}, CriticalityLevel.CRITICAL),
    ],
)
def test_criticality_mapping(severity_fields, expected_criticality) -> None:
    assert normalize({"itime": 1761724800, **severity_fields}).criticite_source == expected_criticality


def test_event_date_prefers_eventtime_in_any_unit_then_itime_then_local_date() -> None:
    expected_datetime = datetime(2025, 10, 29, 8, 0, tzinfo=UTC)
    epoch_seconds = int(expected_datetime.timestamp())

    assert normalize({"level": "alert", "eventtime": epoch_seconds * 10**9, "itime": 1}).date_evenement == expected_datetime
    assert normalize({"level": "alert", "eventtime": epoch_seconds * 1000}).date_evenement == expected_datetime
    assert normalize({"level": "alert", "itime": str(epoch_seconds)}).date_evenement == expected_datetime
    # 09:00 à Paris le 29 octobre 2025 = 08:00 UTC (heure d'hiver).
    assert normalize({"level": "alert", "date": "2025-10-29", "time": "09:00:00"}).date_evenement == expected_datetime


def test_type_comes_from_subtype_then_type() -> None:
    assert normalize({"itime": 1, "level": "alert", "type": "utm", "subtype": "ips"}).type == "ips"
    assert normalize({"itime": 1, "level": "alert", "type": "event"}).type == "event"
    assert normalize({"itime": 1, "level": "alert"}).type == "inconnu"


@pytest.mark.parametrize(
    "invalid_log",
    [
        {"itime": 1},  # aucune sévérité
        {"itime": 1, "level": "inconnu"},  # sévérité inconnue
        {"level": "alert"},  # aucune date
        {"level": "alert", "itime": "pas-une-date"},
        {"level": "alert", "date": "29/10/2025", "time": "09:00"},
    ],
)
def test_invalid_logs_are_rejected(invalid_log) -> None:
    with pytest.raises(InvalidFortiAnalyzerLogError):
        normalize(invalid_log)


def test_identifier_is_stable_and_independent_of_field_order() -> None:
    first_identifier = compute_source_identifier({"itime": 1, "level": "alert", "msg": "x"})

    assert first_identifier == compute_source_identifier({"msg": "x", "level": "alert", "itime": 1})
    assert first_identifier != compute_source_identifier({"itime": 2, "level": "alert", "msg": "x"})
    assert first_identifier.startswith("faz-") and len(first_identifier) == 68


def test_local_date_uses_the_tz_field_of_the_log_before_the_configured_timezone() -> None:
    # tz="+0100" (champ des logs transférés par syslog) : 10:05:32 locale = 09:05:32 UTC, quel que soit le fuseau configuré.
    assert normalize({"level": "alert", "date": "2026-10-30", "time": "10:05:32", "tz": "+0100"}).date_evenement == (
        datetime(2026, 10, 30, 9, 5, 32, tzinfo=UTC)
    )


def test_identifier_ignores_syslog_reception_metadata() -> None:
    fortianalyzer_fields = {"itime": 1, "level": "alert", "msg": "x"}

    assert compute_source_identifier(fortianalyzer_fields) == compute_source_identifier(
        {**fortianalyzer_fields, SYSLOG_RECEPTION_METADATA_FIELD: {"recu_le": "2026-10-30T09:05:33+00:00"}}
    )
