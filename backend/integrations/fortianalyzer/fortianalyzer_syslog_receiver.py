"""Réception des logs que FortiAnalyzer transfère par syslog (UDP et/ou TCP), en écoute permanente.

FortiAnalyzer POUSSE ses logs (« log forwarding ») : l'application n'interroge rien, elle écoute un port. Chaque
message reçu est lu (`fortianalyzer_syslog_message_parser.py`) puis placé dans une file d'attente en mémoire ; la
collecte (`log_collection`) vide cette file à chaque passage (`take_new_logs`) pour enregistrer les logs en base.

Choix et limites :
- UDP : un seul fil d'exécution (traiter un datagramme ne fait que lire des champs : rapide) ; TCP : un fil par
  connexion, un message par ligne (encadrement « octet-counting » RFC 6587 toléré : le préfixe de longueur est retiré).
- File bornée (`maximum_pending_logs`) : si la collecte ne suit pas, les messages en trop sont PERDUS et comptés,
  plutôt que de saturer la mémoire. FortiAnalyzer conserve de son côté tous ses logs.
- La file est en mémoire : les logs reçus mais pas encore collectés sont perdus si l'application s'arrête. D'où une
  collecte fréquente (LOG_COLLECTION_INTERVAL_SECONDS).
- Émetteurs filtrables (`allowed_sender_addresses`) : sans filtre, n'importe quelle machine du réseau peut envoyer
  de faux logs sur le port. Le syslog n'a ni authentification ni chiffrement.
"""

import logging
import re
import socketserver
import sys
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.integrations.fortianalyzer.critical_log_source import RawFortiAnalyzerLog
from backend.integrations.fortianalyzer.fortianalyzer_errors import SyslogReceptionError
from backend.integrations.fortianalyzer.fortianalyzer_syslog_message_parser import (
    MAXIMUM_SYSLOG_MESSAGE_CHARACTERS,
    ReceivedSyslogMessage,
    parse_fortianalyzer_syslog_message,
)

syslog_receiver_logger = logging.getLogger(__name__)

SYSLOG_MESSAGE_ENCODING = "utf-8"
# Un datagramme UDP ne dépasse jamais 65 535 octets.
MAXIMUM_UDP_DATAGRAM_BYTES = 65_535
# Préfixe de longueur de l'encadrement « octet-counting » (RFC 6587) : « 1234 <189>logver=... ».
TCP_OCTET_COUNTING_PREFIX_REGEX = re.compile(r"^\d+ (?=<)")


@dataclass(frozen=True)
class SyslogReceptionParameters:
    """Paramètres d'écoute, construits depuis le .env (voir `log_source_selection.py`)."""

    listen_address: str = "0.0.0.0"
    listen_port: int = 5140
    is_udp_enabled: bool = True
    is_tcp_enabled: bool = True
    # Vide = tous les émetteurs acceptés.
    allowed_sender_addresses: frozenset[str] = field(default_factory=frozenset)
    maximum_pending_logs: int = 100_000


@dataclass(frozen=True)
class SyslogReceptionStatistics:
    """Compteurs depuis le démarrage de l'écoute (affichés dans la page Journaux)."""

    is_listening: bool
    pending_log_count: int
    accepted_message_count: int
    rejected_sender_message_count: int
    unreadable_message_count: int
    dropped_because_queue_full_count: int


class FortiAnalyzerSyslogReceiver:
    """Source d'alertes réelle (respecte le contrat `CriticalLogSource`)."""

    def __init__(
        self,
        reception_parameters: SyslogReceptionParameters,
        current_time_function: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """`current_time_function` ne sert qu'aux tests (heure de réception fixe)."""
        self._reception_parameters = reception_parameters
        self._current_time = current_time_function
        self._pending_logs: deque[RawFortiAnalyzerLog] = deque()
        # Protège la file et les compteurs : UDP, chaque connexion TCP et la collecte sont des fils différents.
        self._state_lock = threading.Lock()
        self._servers: list[socketserver.BaseServer] = []
        self._accepted_message_count = 0
        self._rejected_sender_message_count = 0
        self._unreadable_message_count = 0
        self._dropped_because_queue_full_count = 0

    @property
    def source_description(self) -> str:
        protocols = "/".join(self._enabled_protocols()) or "aucun protocole"
        return (
            f"Syslog FortiAnalyzer ({protocols} {self._reception_parameters.listen_address}:"
            f"{self._reception_parameters.listen_port})"
        )

    @property
    def is_listening(self) -> bool:
        return bool(self._servers)

    def start(self) -> None:
        """Ouvre les ports d'écoute. Lève SyslogReceptionError si un port ne peut pas être ouvert (déjà utilisé...)."""
        if self.is_listening:
            return
        server_address = (self._reception_parameters.listen_address, self._reception_parameters.listen_port)
        try:
            if self._reception_parameters.is_udp_enabled:
                self._servers.append(_SyslogUdpServer(server_address, self))
            if self._reception_parameters.is_tcp_enabled:
                self._servers.append(_SyslogTcpServer(server_address, self))
        except OSError as socket_error:
            self.stop()
            raise SyslogReceptionError(
                f"Impossible d'écouter sur {server_address[0]}:{server_address[1]} "
                f"({socket_error.strerror or type(socket_error).__name__}). Port déjà utilisé ou droits insuffisants ?"
            ) from socket_error
        for server in self._servers:
            threading.Thread(target=server.serve_forever, name=f"syslog-{type(server).__name__}", daemon=True).start()
        syslog_receiver_logger.info("Réception syslog active : %s.", self.source_description)

    def stop(self) -> None:
        """Ferme les ports. Les logs encore en file restent disponibles pour une dernière collecte."""
        for server in self._servers:
            server.shutdown()
            server.server_close()
        self._servers = []

    @property
    def listening_port(self) -> int | None:
        """Port réellement ouvert (utile quand le port demandé est 0 : choisi par le système, cas des tests)."""
        return self._servers[0].server_address[1] if self._servers else None

    def take_new_logs(self, period_start: datetime, period_end: datetime) -> list[RawFortiAnalyzerLog]:
        """Vide la file d'attente et retourne les logs reçus depuis l'appel précédent (bornes ignorées).

        Lève SyslogReceptionError si l'écoute n'est pas active ET qu'aucun log n'attend : sinon la collecte
        « réussirait » sans rien recevoir et la panne passerait inaperçue.
        """
        with self._state_lock:
            if not self._servers and not self._pending_logs:
                raise SyslogReceptionError("La réception syslog n'est pas active : aucun port n'est à l'écoute.")
            taken_logs = list(self._pending_logs)
            self._pending_logs.clear()
        return taken_logs

    def read_reception_statistics(self) -> SyslogReceptionStatistics:
        with self._state_lock:
            return SyslogReceptionStatistics(
                is_listening=bool(self._servers),
                pending_log_count=len(self._pending_logs),
                accepted_message_count=self._accepted_message_count,
                rejected_sender_message_count=self._rejected_sender_message_count,
                unreadable_message_count=self._unreadable_message_count,
                dropped_because_queue_full_count=self._dropped_because_queue_full_count,
            )

    def handle_received_text(self, received_text: str, sender_address: str, protocol: str) -> None:
        """Traite un message reçu : filtre de l'émetteur, validation, lecture, mise en file. Ne lève jamais.

        Public pour les tests : permet de simuler une réception sans ouvrir de port.
        """
        allowed_sender_addresses = self._reception_parameters.allowed_sender_addresses
        if allowed_sender_addresses and sender_address not in allowed_sender_addresses:
            with self._state_lock:
                self._rejected_sender_message_count += 1
            return
        if not received_text.strip():
            return
        try:
            parsed_log = parse_fortianalyzer_syslog_message(
                ReceivedSyslogMessage(
                    text=received_text,
                    sender_address=sender_address,
                    protocol=protocol,
                    received_at=self._current_time(),
                )
            )
        except ValidationError:
            parsed_log = None
        with self._state_lock:
            if parsed_log is None:
                self._unreadable_message_count += 1
            elif len(self._pending_logs) >= self._reception_parameters.maximum_pending_logs:
                self._dropped_because_queue_full_count += 1
                # Un avertissement par tranche de 1000 pertes : assez pour être vu, sans inonder les journaux.
                if self._dropped_because_queue_full_count % 1000 == 1:
                    syslog_receiver_logger.warning(
                        "File syslog pleine (%s logs) : messages perdus. Collecter plus souvent.",
                        self._reception_parameters.maximum_pending_logs,
                    )
            else:
                self._pending_logs.append(parsed_log)
                self._accepted_message_count += 1

    def _enabled_protocols(self) -> list[str]:
        return [
            protocol
            for protocol, is_enabled in (
                ("UDP", self._reception_parameters.is_udp_enabled),
                ("TCP", self._reception_parameters.is_tcp_enabled),
            )
            if is_enabled
        ]


# --- Serveurs réseau (bibliothèque standard socketserver) ---


class _SyslogUdpRequestHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        datagram_bytes, _socket = self.request
        datagram_text = datagram_bytes.decode(SYSLOG_MESSAGE_ENCODING, errors="replace")
        # Un datagramme contient normalement un seul log ; plusieurs lignes sont traitées une par une.
        for message_line in datagram_text.splitlines():
            self.server.syslog_receiver.handle_received_text(message_line, self.client_address[0], "UDP")


class _SyslogTcpRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        while True:
            # Lecture bornée : une « ligne » sans fin ne doit pas saturer la mémoire.
            line_bytes = self.rfile.readline(MAXIMUM_SYSLOG_MESSAGE_CHARACTERS + 1)
            if not line_bytes:
                return
            line_text = line_bytes.decode(SYSLOG_MESSAGE_ENCODING, errors="replace")
            line_text = TCP_OCTET_COUNTING_PREFIX_REGEX.sub("", line_text.lstrip())
            self.server.syslog_receiver.handle_received_text(line_text, self.client_address[0], "TCP")


class _SyslogUdpServer(socketserver.UDPServer):
    max_packet_size = MAXIMUM_UDP_DATAGRAM_BYTES

    def __init__(self, server_address: tuple[str, int], syslog_receiver: FortiAnalyzerSyslogReceiver) -> None:
        self.syslog_receiver = syslog_receiver
        super().__init__(server_address, _SyslogUdpRequestHandler)


class _SyslogTcpServer(socketserver.ThreadingTCPServer):
    # Redémarrage rapide sous Linux (port en TIME_WAIT). Pas sous Windows : l'option y permet d'occuper un port déjà pris.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], syslog_receiver: FortiAnalyzerSyslogReceiver) -> None:
        self.syslog_receiver = syslog_receiver
        super().__init__(server_address, _SyslogTcpRequestHandler)
