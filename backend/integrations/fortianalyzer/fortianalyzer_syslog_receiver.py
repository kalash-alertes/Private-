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
- Tampon de réception UDP agrandi (`UDP_RECEIVE_BUFFER_BYTES`) : FortiAnalyzer envoie par rafales ; avec le tampon
  par défaut du noyau (~208 Kio), des datagrammes étaient perdus AVANT d'atteindre l'application (mesuré : ~1,3 %
  de pertes). Ces pertes système sont lisibles dans /proc/net/snmp (`read_system_udp_receive_buffer_error_count`).
- Les derniers messages reçus (lisibles ou non, AVANT tout filtre de sévérité) sont gardés dans une mémoire bornée
  pour la page « Logs bruts » ; un compteur par niveau de sévérité source explique l'écart entre logs reçus et
  logs enregistrés.
"""

import logging
import re
import socket
import socketserver
import sys
import threading
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from backend.integrations.fortianalyzer.fortianalyzer_log_source import RawFortiAnalyzerLog
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
# Tampon demandé au noyau pour le port UDP. Linux le plafonne à net.core.rmem_max (4 Mio dans le conteneur actuel)
# puis le double : ~8 Mio, soit plusieurs milliers de logs d'avance pendant une rafale.
UDP_RECEIVE_BUFFER_BYTES = 4 * 1024 * 1024
# Compteurs UDP du noyau (Linux). Dans un conteneur, ils ne concernent que le réseau du conteneur.
LINUX_NETWORK_SNMP_STATISTICS_FILE = Path("/proc/net/snmp")
# Libellé du compteur par niveau pour un message lisible sans champ `severity` ni `level`.
MISSING_SEVERITY_LABEL = "(aucun)"


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
    # Derniers messages gardés pour l'affichage brut (0 = aucun).
    recent_messages_kept_for_display: int = 2_000


@dataclass(frozen=True)
class SyslogReceptionStatistics:
    """Compteurs depuis le démarrage de l'écoute (affichés dans les pages Journaux et Logs bruts)."""

    is_listening: bool
    pending_log_count: int
    accepted_message_count: int
    rejected_sender_message_count: int
    unreadable_message_count: int
    dropped_because_queue_full_count: int
    # Messages lisibles par valeur brute du niveau (`severity`, sinon `level`), ex. {"notice": 120, "error": 3}.
    accepted_message_count_by_severity_label: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RecentlyReceivedSyslogMessage:
    """Un message tel que reçu, gardé pour l'affichage brut. `parsed_log` vaut None si le message est illisible."""

    sequence_number: int
    received_at: datetime
    sender_address: str
    protocol: str
    raw_text: str
    parsed_log: RawFortiAnalyzerLog | None


def read_severity_label(parsed_log: RawFortiAnalyzerLog) -> str:
    """Valeur brute du niveau d'un log Fortinet : `severity` (logs d'attaque) prioritaire, sinon `level`."""
    for severity_field in ("severity", "level"):
        severity_value = str(parsed_log.get(severity_field) or "").strip().lower()
        if severity_value:
            return severity_value
    return MISSING_SEVERITY_LABEL


def read_system_udp_receive_buffer_error_count() -> int | None:
    """Datagrammes UDP jetés par le noyau faute de place dans un tampon de réception (`RcvbufErrors`), tous ports
    confondus, depuis le démarrage du réseau (du conteneur). None hors Linux ou si le fichier est illisible.

    Ces pertes ont lieu AVANT l'application : aucun autre compteur ne peut les voir.
    """
    try:
        snmp_lines = [
            line.split() for line in LINUX_NETWORK_SNMP_STATISTICS_FILE.read_text().splitlines() if line.startswith("Udp:")
        ]
        header_line, value_line = snmp_lines[0], snmp_lines[1]
        return int(value_line[header_line.index("RcvbufErrors")])
    except (OSError, IndexError, ValueError):
        return None


class FortiAnalyzerSyslogReceiver:
    """Source d'alertes réelle (respecte le contrat `FortiAnalyzerLogSource`)."""

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
        self._accepted_message_count_by_severity_label: Counter[str] = Counter()
        self._recent_messages: deque[RecentlyReceivedSyslogMessage] = deque(
            maxlen=max(reception_parameters.recent_messages_kept_for_display, 0)
        )
        self._last_sequence_number = 0
        # Compteur système de pertes UDP au démarrage de l'écoute : il est cumulé depuis le démarrage du réseau du
        # conteneur, seule la différence concerne la réception en cours.
        self._udp_receive_buffer_errors_at_start: int | None = None

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
        self._udp_receive_buffer_errors_at_start = read_system_udp_receive_buffer_error_count()
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
                accepted_message_count_by_severity_label=dict(self._accepted_message_count_by_severity_label),
            )

    def count_udp_datagrams_lost_by_system_since_start(self) -> int | None:
        """Datagrammes UDP jetés par le noyau (tampon plein) depuis le démarrage de l'écoute ; None si non mesurable."""
        current_error_count = read_system_udp_receive_buffer_error_count()
        if current_error_count is None or self._udp_receive_buffer_errors_at_start is None:
            return None
        return max(current_error_count - self._udp_receive_buffer_errors_at_start, 0)

    def read_recent_messages(self, after_sequence_number: int = 0) -> list[RecentlyReceivedSyslogMessage]:
        """Retourne les messages gardés pour l'affichage dont le numéro dépasse `after_sequence_number`, du plus
        ancien au plus récent. Ne retire rien : la collecte n'est pas affectée."""
        with self._state_lock:
            return [message for message in self._recent_messages if message.sequence_number > after_sequence_number]

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
        received_at = self._current_time()
        try:
            parsed_log = parse_fortianalyzer_syslog_message(
                ReceivedSyslogMessage(
                    text=received_text, sender_address=sender_address, protocol=protocol, received_at=received_at
                )
            )
        except ValidationError:
            parsed_log = None
        with self._state_lock:
            self._remember_recent_message(received_text, sender_address, protocol, received_at, parsed_log)
            if parsed_log is not None:
                self._accepted_message_count_by_severity_label[read_severity_label(parsed_log)] += 1
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

    def _remember_recent_message(
        self,
        received_text: str,
        sender_address: str,
        protocol: str,
        received_at: datetime,
        parsed_log: RawFortiAnalyzerLog | None,
    ) -> None:
        """À appeler sous `_state_lock`. Le texte est tronqué à la taille maximale admise d'un message."""
        if self._recent_messages.maxlen == 0:
            return
        self._last_sequence_number += 1
        self._recent_messages.append(
            RecentlyReceivedSyslogMessage(
                sequence_number=self._last_sequence_number,
                received_at=received_at,
                sender_address=sender_address,
                protocol=protocol,
                raw_text=received_text.strip()[:MAXIMUM_SYSLOG_MESSAGE_CHARACTERS],
                parsed_log=parsed_log,
            )
        )

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

    def server_bind(self) -> None:
        # Agrandit le tampon AVANT l'ouverture du port (voir UDP_RECEIVE_BUFFER_BYTES). Un refus du système n'empêche
        # pas l'écoute : le tampon par défaut reste utilisé, et c'est journalisé.
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RECEIVE_BUFFER_BYTES)
        except OSError as buffer_error:
            syslog_receiver_logger.warning("Tampon UDP non agrandi : %s", buffer_error)
        super().server_bind()
        syslog_receiver_logger.info(
            "Tampon de réception UDP : %s octets.", self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        )


class _SyslogTcpServer(socketserver.ThreadingTCPServer):
    # Redémarrage rapide sous Linux (port en TIME_WAIT). Pas sous Windows : l'option y permet d'occuper un port déjà pris.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], syslog_receiver: FortiAnalyzerSyslogReceiver) -> None:
        self.syslog_receiver = syslog_receiver
        super().__init__(server_address, _SyslogTcpRequestHandler)
