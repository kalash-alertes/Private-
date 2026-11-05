"""Tests du flux des logs bruts : filtres, devenir (enregistré/écarté) selon le seuil, répartition par niveau.

Le récepteur est un vrai `FortiAnalyzerSyslogReceiver` alimenté sans réseau (`handle_received_text`) ; messages
synthétiques (adresses de documentation 192.0.2.0/24).
"""

from datetime import UTC, datetime

from backend.core.criticality import CriticalityLevel
from backend.core.settings import get_application_settings
from backend.features.raw_syslog_feed import service as raw_syslog_feed_service
from backend.features.raw_syslog_feed.schemas import CollectionOutcomeFilter, RawSyslogFeedFilters
from backend.integrations.fortianalyzer import log_source_selection
from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
    FortiAnalyzerSyslogReceiver,
    SyslogReceptionParameters,
)

SENDER_ADDRESS = "192.0.2.104"
NOTICE_MESSAGE = (
    '<189>devname="FGT-SYNTHETIQUE" type="traffic" subtype="forward" level="notice" srcip="192.0.2.11" action="deny"'
)
ERROR_MESSAGE = (
    '<187>devname="FGT-SYNTHETIQUE" type="event" subtype="vpn" level="error" logdesc="IPsec phase 1 error" '
    'remip="192.0.2.50"'
)


def install_receiver_with_messages(monkeypatch, *messages: str) -> None:
    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    get_application_settings.cache_clear()
    receiver = FortiAnalyzerSyslogReceiver(
        SyslogReceptionParameters(), current_time_function=lambda: datetime(2026, 11, 3, 16, 0, tzinfo=UTC)
    )
    for message in messages:
        receiver.handle_received_text(message, SENDER_ADDRESS, "UDP")
    monkeypatch.setattr(log_source_selection, "_shared_syslog_receiver", receiver)


def read_feed(**filter_values):
    return raw_syslog_feed_service.read_raw_syslog_feed(get_application_settings(), RawSyslogFeedFilters(**filter_values))


def test_feed_shows_every_message_newest_first_with_what_the_collection_will_do(monkeypatch) -> None:
    install_receiver_with_messages(monkeypatch, NOTICE_MESSAGE, ERROR_MESSAGE, "texte illisible")

    feed = read_feed()

    assert [message.numero for message in feed.messages] == [3, 2, 1] and feed.dernier_numero == 3
    unreadable, error_log, notice_log = feed.messages
    assert not unreadable.est_lisible and not unreadable.est_enregistre_par_la_collecte
    assert error_log.criticite_source == CriticalityLevel.HIGH and error_log.est_enregistre_par_la_collecte
    assert error_log.resume == "IPsec phase 1 error" and error_log.type == "vpn"
    assert error_log.equipement == "FGT-SYNTHETIQUE"
    assert "reception_syslog" not in error_log.champs and error_log.champs["remip"] == "192.0.2.50"
    # Seuil par défaut des tests : moyenne. Un log « notice » (faible) est lu puis écarté.
    assert notice_log.criticite_source == CriticalityLevel.LOW and not notice_log.est_enregistre_par_la_collecte
    assert notice_log.motif_non_enregistrement == raw_syslog_feed_service.BELOW_THRESHOLD_REASON


def test_feed_filters_and_returns_only_new_messages(monkeypatch) -> None:
    install_receiver_with_messages(monkeypatch, NOTICE_MESSAGE, ERROR_MESSAGE, NOTICE_MESSAGE)

    def numbers(**filter_values) -> list[int]:
        return [message.numero for message in read_feed(**filter_values).messages]

    assert numbers(enregistrement=CollectionOutcomeFilter.STORED) == [2]
    assert numbers(enregistrement=CollectionOutcomeFilter.DISCARDED) == [3, 1]
    assert numbers(criticite=CriticalityLevel.LOW) == [3, 1]
    assert numbers(recherche="192.0.2.50") == [2]
    assert numbers(apres=2) == [3]
    assert numbers(limite=1) == [3]


def test_combined_filters_search_without_case_and_advance_past_nonmatching_messages(monkeypatch) -> None:
    install_receiver_with_messages(monkeypatch, NOTICE_MESSAGE, ERROR_MESSAGE, NOTICE_MESSAGE, "illisible")

    feed = read_feed(criticite=CriticalityLevel.HIGH, enregistrement=CollectionOutcomeFilter.STORED, recherche="  IPSEC  ")

    assert [message.numero for message in feed.messages] == [2]
    assert feed.dernier_numero == 4
    assert read_feed(criticite=CriticalityLevel.HIGH, enregistrement=CollectionOutcomeFilter.DISCARDED).messages == []
    assert read_feed(recherche="texte absent").dernier_numero == 4
    assert read_feed(apres=feed.dernier_numero).messages == []


def test_statistics_explain_received_versus_stored(monkeypatch) -> None:
    install_receiver_with_messages(
        monkeypatch, NOTICE_MESSAGE, NOTICE_MESSAGE, NOTICE_MESSAGE, ERROR_MESSAGE, "illisible"
    )

    statistics = read_feed().statistiques

    assert (statistics.nb_messages_lisibles, statistics.nb_messages_enregistrables) == (4, 1)
    assert statistics.nb_messages_ecartes_par_le_seuil == 3 and statistics.nb_messages_illisibles == 1
    notice_level, error_level = statistics.repartition_par_niveau
    assert (notice_level.niveau_source, notice_level.nombre, notice_level.pourcentage) == ("notice", 3, 75.0)
    assert not notice_level.est_enregistre_par_la_collecte
    assert error_level.niveau_source == "error" and error_level.est_enregistre_par_la_collecte


def test_feed_is_empty_in_demo_mode() -> None:
    feed = read_feed()

    assert feed.messages == [] and feed.statistiques.est_en_mode_demo and feed.statistiques.nb_messages_lisibles == 0
