#!/usr/bin/env python3
"""
Récepteur syslog (UDP + TCP) pour les logs forwardés par FortiAnalyzer.
Usage : python3 syslog_receiver.py
"""

import socketserver
import threading
import re
import datetime

# ===================== VARIABLES DE CONFIG =====================
LISTEN_IP = "0.0.0.0"        # écoute sur toutes les interfaces
LISTEN_PORT = 5140           # 514 nécessite root/admin ; 5140 est plus simple
ENABLE_UDP = True
ENABLE_TCP = True
LOG_FILE = "fortianalyzer_logs.log"   # None pour désactiver l'écriture fichier
PRINT_CONSOLE = True
PARSE_KEYVALUE = True        # parse les champs Fortinet clé=valeur
ENCODING = "utf-8"
# ===============================================================

KV_REGEX = re.compile(r'(\w+)=("([^"]*)"|\S+)')
file_lock = threading.Lock()


def parse_fortinet(message: str) -> dict:
    """Extrait les champs clé=valeur d'un log Fortinet."""
    fields = {}
    for m in KV_REGEX.finditer(message):
        key = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(2)
        fields[key] = value
    return fields


def handle_message(raw: str, source_ip: str, proto: str):
    raw = raw.strip()
    if not raw:
        return

    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    parsed = parse_fortinet(raw) if PARSE_KEYVALUE else {}

    if PRINT_CONSOLE:
        print(f"[{timestamp}] [{proto}] {source_ip} -> {raw}")
        if parsed:
            # exemple : afficher quelques champs utiles s'ils existent
            keys = ("type", "subtype", "srcip", "dstip", "action", "devname")
            summary = {k: parsed[k] for k in keys if k in parsed}
            if summary:
                print(f"    parsed: {summary}")

    if LOG_FILE:
        with file_lock:
            with open(LOG_FILE, "a", encoding=ENCODING) as f:
                f.write(f"{timestamp} {proto} {source_ip} {raw}\n")

    # >>> ICI : envoyer vers ton app (API, base de données, queue, etc.)


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, _sock = self.request
        handle_message(data.decode(ENCODING, errors="replace"),
                       self.client_address[0], "UDP")


class TCPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            handle_message(line.decode(ENCODING, errors="replace"),
                           self.client_address[0], "TCP")


class ThreadedUDP(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass


class ThreadedTCP(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    servers = []
    if ENABLE_UDP:
        servers.append(ThreadedUDP((LISTEN_IP, LISTEN_PORT), UDPHandler))
    if ENABLE_TCP:
        servers.append(ThreadedTCP((LISTEN_IP, LISTEN_PORT), TCPHandler))

    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()

    print(f"Récepteur syslog en écoute sur {LISTEN_IP}:{LISTEN_PORT} "
          f"(UDP={ENABLE_UDP}, TCP={ENABLE_TCP}) - Ctrl+C pour arrêter")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nArrêt...")
        for s in servers:
            s.shutdown()


if __name__ == "__main__":
    main()