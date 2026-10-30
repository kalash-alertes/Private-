"""Lecture d'un message syslog envoyé par FortiAnalyzer (transfert de logs, « log forwarding »).

Forme observée sur le FortiAnalyzer de l'équipe (sans en-tête RFC 3164/5424, directement les champs) :
    <189>logver=702101706 timestamp=1793354732 devname="FGINTELL" ... level="notice" srcip="..." ...
- `<189>` : priorité syslog (facilité × 8 + gravité syslog), conservée dans les métadonnées de réception ;
- puis des paires `clé=valeur` Fortinet, la valeur étant entre guillemets si elle contient des espaces.
Un éventuel en-tête syslog (date, nom d'hôte) avant les champs est simplement ignoré : seules les paires sont lues.

Le message reçu est validé (Pydantic) avant lecture : adresse de l'émetteur, protocole, taille maximale.
"""

import re
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal

from pydantic import BaseModel, Field

from backend.integrations.fortianalyzer.critical_log_source import SYSLOG_RECEPTION_METADATA_FIELD, RawFortiAnalyzerLog

# Garde-fou : un log Fortinet fait quelques kilo-octets ; au-delà, le message est refusé (erreur ou envoi hostile).
MAXIMUM_SYSLOG_MESSAGE_CHARACTERS = 65_535
SYSLOG_PRIORITY_REGEX = re.compile(r"^<(\d{1,3})>")
# Même expression que le script de test de connexion syslog : clé, puis valeur entre guillemets ou sans espace.
FORTINET_KEY_VALUE_REGEX = re.compile(r'(\w+)=("([^"]*)"|\S+)')


class ReceivedSyslogMessage(BaseModel):
    """Un message tel qu'il arrive sur le port syslog, avant lecture de ses champs."""

    text: str = Field(max_length=MAXIMUM_SYSLOG_MESSAGE_CHARACTERS)
    sender_address: IPv4Address | IPv6Address
    protocol: Literal["UDP", "TCP"]
    received_at: datetime


def parse_fortianalyzer_syslog_message(received_message: ReceivedSyslogMessage) -> RawFortiAnalyzerLog | None:
    """Retourne les champs Fortinet du message, plus les métadonnées de réception.

    Retourne None si le message ne contient aucune paire `clé=valeur` (ce n'est pas un log Fortinet).
    """
    message_text = received_message.text.strip()
    priority_match = SYSLOG_PRIORITY_REGEX.match(message_text)
    fields_text = message_text[priority_match.end():] if priority_match else message_text

    fortinet_fields: RawFortiAnalyzerLog = {}
    for key_value_match in FORTINET_KEY_VALUE_REGEX.finditer(fields_text):
        quoted_value = key_value_match.group(3)
        fortinet_fields[key_value_match.group(1)] = (
            quoted_value if quoted_value is not None else key_value_match.group(2)
        )
    if not fortinet_fields:
        return None

    fortinet_fields[SYSLOG_RECEPTION_METADATA_FIELD] = {
        "adresse_emetteur": str(received_message.sender_address),
        "protocole": received_message.protocol,
        "recu_le": received_message.received_at.isoformat(),
        "priorite_syslog": int(priority_match.group(1)) if priority_match else None,
    }
    return fortinet_fields
