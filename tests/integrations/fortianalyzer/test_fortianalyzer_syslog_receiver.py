"""Tests de la réception syslog : lecture des messages Fortinet, filtre des émetteurs, file d'attente, sockets locaux.

Les messages sont synthétiques (adresses réservées à la documentation : 192.0.2.0/24, 198.51.100.0/24), au format
observé sur le FortiAnalyzer de l'équipe. Le test réseau n'utilise que la boucle locale (127.0.0.1, port libre).
"""

import socket
import time
from datetime import UTC, datetime

import pytest

from backend.integrations.fortianalyzer.critical_log_source import SYSLOG_RECEPTION_METADATA_FIELD
from backend.integrations.fortianalyzer.fortianalyzer_errors import SyslogReceptionError
from backend.integrations.fortianalyzer.fortianalyzer_syslog_message_parser import (
    ReceivedSyslogMessage,
    parse_fortianalyzer_syslog_message,
)
from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
    FortiAnalyzerSyslogReceiver,
    SyslogReceptionParameters,
)

RECEPTION_TIME = datetime(2026, 10, 30, 9, 5, 33, tzinfo=UTC)
FORTIANALYZER_ADDRESS = "192.0.2.104"
SYNTHETIC_SYSLOG_MESSAGE = (
    '<189>logver=702101706 timestamp=1793354732 devname="FGT-SYNTHETIQUE" devid="FGSYNTH0001" vd="root" '
    'date="2026-10-30" time="10:05:32" eventtime=1793351131937197975 tz="+0100" logid="0000000013" '
    'type="traffic" subtype="forward" level="notice" srcip="192.0.2.11" dstip="198.51.100.8" dstport=53 '
    'action="deny" service="DNS" vwlquality="Seq_num(6 port4), alive, sla(0x1)"'
)


def build_receiver(**parameter_values) -> FortiAnalyzerSyslogReceiver:
    return FortiAnalyzerSyslogReceiver(
        SyslogReceptionParameters(**parameter_values), current_time_function=lambda: RECEPTION_TIME
    )


def test_fortinet_fields_and_reception_metadata_are_read() -> None:
    parsed_log = parse_fortianalyzer_syslog_message(
        ReceivedSyslogMessage(
            text=SYNTHETIC_SYSLOG_MESSAGE, sender_address=FORTIANALYZER_ADDRESS, protocol="UDP", received_at=RECEPTION_TIME
        )
    )

    assert parsed_log["logver"] == "702101706"  # la priorité <189> ne colle pas au premier champ
    assert parsed_log["devname"] == "FGT-SYNTHETIQUE" and parsed_log["level"] == "notice"
    assert parsed_log["eventtime"] == "1793351131937197975"
    # Valeur entre guillemets contenant des espaces et des virgules : lue en entier.
    assert parsed_log["vwlquality"] == "Seq_num(6 port4), alive, sla(0x1)"
    assert parsed_log[SYSLOG_RECEPTION_METADATA_FIELD] == {
        "adresse_emetteur": FORTIANALYZER_ADDRESS,
        "protocole": "UDP",
        "recu_le": RECEPTION_TIME.isoformat(),
        "priorite_syslog": 189,
    }


def test_received_messages_are_queued_then_taken_once() -> None:
    receiver = build_receiver()
    receiver._servers = [object()]  # écoute considérée active, sans ouvrir de port

    receiver.handle_received_text(SYNTHETIC_SYSLOG_MESSAGE, FORTIANALYZER_ADDRESS, "UDP")
    receiver.handle_received_text("ceci n'est pas un log Fortinet", FORTIANALYZER_ADDRESS, "UDP")
    receiver.handle_received_text("   ", FORTIANALYZER_ADDRESS, "UDP")

    taken_logs = receiver.take_new_logs(RECEPTION_TIME, RECEPTION_TIME)
    statistics = receiver.read_reception_statistics()
    assert [log["devid"] for log in taken_logs] == ["FGSYNTH0001"]
    assert receiver.take_new_logs(RECEPTION_TIME, RECEPTION_TIME) == []
    assert (statistics.accepted_message_count, statistics.unreadable_message_count) == (1, 1)


def test_senders_outside_the_allowed_list_are_refused() -> None:
    receiver = build_receiver(allowed_sender_addresses=frozenset({FORTIANALYZER_ADDRESS}))
    receiver._servers = [object()]

    receiver.handle_received_text(SYNTHETIC_SYSLOG_MESSAGE, "198.51.100.66", "UDP")
    receiver.handle_received_text(SYNTHETIC_SYSLOG_MESSAGE, FORTIANALYZER_ADDRESS, "TCP")

    assert len(receiver.take_new_logs(RECEPTION_TIME, RECEPTION_TIME)) == 1
    assert receiver.read_reception_statistics().rejected_sender_message_count == 1


def test_full_queue_drops_and_counts_new_messages() -> None:
    receiver = build_receiver(maximum_pending_logs=2)
    for _ in range(3):
        receiver.handle_received_text(SYNTHETIC_SYSLOG_MESSAGE, FORTIANALYZER_ADDRESS, "UDP")

    statistics = receiver.read_reception_statistics()
    assert (statistics.pending_log_count, statistics.dropped_because_queue_full_count) == (2, 1)


def test_oversized_message_is_counted_as_unreadable() -> None:
    receiver = build_receiver()
    receiver.handle_received_text("level=alert " + "x" * 70_000, FORTIANALYZER_ADDRESS, "UDP")

    assert receiver.read_reception_statistics().unreadable_message_count == 1


def test_taking_logs_from_an_inactive_receiver_fails_loudly() -> None:
    with pytest.raises(SyslogReceptionError, match="pas active"):
        build_receiver().take_new_logs(RECEPTION_TIME, RECEPTION_TIME)


def wait_for_pending_logs(receiver: FortiAnalyzerSyslogReceiver, expected_count: int) -> None:
    deadline = time.monotonic() + 5
    while receiver.read_reception_statistics().pending_log_count < expected_count and time.monotonic() < deadline:
        time.sleep(0.02)


@pytest.mark.parametrize("protocol", ["UDP", "TCP"])
def test_real_sockets_on_loopback_receive_messages(protocol) -> None:
    receiver = build_receiver(
        listen_address="127.0.0.1", listen_port=0, is_udp_enabled=protocol == "UDP", is_tcp_enabled=protocol == "TCP"
    )
    receiver.start()
    try:
        server_address = ("127.0.0.1", receiver.listening_port)
        if protocol == "UDP":
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.sendto(SYNTHETIC_SYSLOG_MESSAGE.encode(), server_address)
        else:
            with socket.create_connection(server_address, timeout=5) as tcp_socket:
                # Deux messages sur la même connexion, le second avec un préfixe « octet-counting » (RFC 6587).
                tcp_socket.sendall(f"{SYNTHETIC_SYSLOG_MESSAGE}\n123 {SYNTHETIC_SYSLOG_MESSAGE}\n".encode())
        expected_count = 1 if protocol == "UDP" else 2
        wait_for_pending_logs(receiver, expected_count)
        taken_logs = receiver.take_new_logs(RECEPTION_TIME, RECEPTION_TIME)
    finally:
        receiver.stop()

    assert len(taken_logs) == expected_count
    assert all(log[SYSLOG_RECEPTION_METADATA_FIELD]["priorite_syslog"] == 189 for log in taken_logs)
    assert not receiver.is_listening


def test_port_already_in_use_raises_a_clear_error() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as occupying_socket:
        occupying_socket.bind(("127.0.0.1", 0))
        occupied_port = occupying_socket.getsockname()[1]
        receiver = build_receiver(listen_address="127.0.0.1", listen_port=occupied_port, is_tcp_enabled=False)

        with pytest.raises(SyslogReceptionError, match="Impossible d'écouter"):
            receiver.start()
    assert not receiver.is_listening
