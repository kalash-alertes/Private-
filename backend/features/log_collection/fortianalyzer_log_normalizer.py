"""Conversion d'un log FortiAnalyzer brut en log de l'application (sévérité, date, type, identifiant de déduplication).

Règles (PROVISOIRES : à confirmer sur les vrais logs du FortiAnalyzer de l'équipe, cf. explain_project.md section 15) :

- **Sévérité** : le champ `severity` (logs d'attaque IPS : critical, high, medium, low, info) est prioritaire ; à
  défaut, le champ `level` (syslog : emergency → debug). Correspondance :
  emergency, alert, critical → critique · error, high → haute · warning, medium → moyenne · notice, low → faible ·
  information, info, debug → information. Une valeur inconnue rend le log invalide (il est compté, pas enregistré).
- **Date de l'événement** : `eventtime` (horodatage de l'équipement, en s, ms, µs ou ns selon la version), sinon
  `itime` (réception par FortiAnalyzer, en secondes), sinon `date` + `time` dans le fuseau du champ `tz` du log
  (ex. `+0100`), à défaut FORTIANALYZER_TIMEZONE.
  Le champ `timestamp` des logs transférés par syslog n'est PAS utilisé : sur le FortiAnalyzer de l'équipe, il est
  décalé du fuseau (heure locale écrite comme si c'était de l'UTC), alors que `eventtime` est juste.
- **Type** (sert aussi de catégorie d'incident, donc au choix du playbook) : `subtype` (ips, virus, system...), sinon
  `type`, sinon « inconnu ».
- **Identifiant de déduplication** : FortiAnalyzer ne fournit pas d'identifiant unique garanti entre équipements ; on
  calcule une empreinte SHA-256 du log complet (champs triés), SANS les métadonnées de réception syslog ajoutées par
  l'application (émetteur, heure de réception) : le même log envoyé deux fois (retransmission, double transfert)
  donne la même empreinte et n'est pas recréé.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

from backend.core.criticality import CriticalityLevel
from backend.integrations.fortianalyzer.critical_log_source import SYSLOG_RECEPTION_METADATA_FIELD

FORTIANALYZER_SEVERITY_TO_CRITICALITY = {
    "emergency": CriticalityLevel.CRITICAL,
    "alert": CriticalityLevel.CRITICAL,
    "critical": CriticalityLevel.CRITICAL,
    "error": CriticalityLevel.HIGH,
    "high": CriticalityLevel.HIGH,
    "warning": CriticalityLevel.MEDIUM,
    "medium": CriticalityLevel.MEDIUM,
    "notice": CriticalityLevel.LOW,
    "low": CriticalityLevel.LOW,
    "information": CriticalityLevel.INFORMATION,
    "info": CriticalityLevel.INFORMATION,
    "debug": CriticalityLevel.INFORMATION,
}
SOURCE_IDENTIFIER_PREFIX = "faz-"
MAXIMUM_TYPE_LENGTH = 255
# Champ `tz` des logs Fortinet : décalage UTC, ex. « +0100 » ou « -0530 ».
FORTINET_TIMEZONE_OFFSET_REGEX = re.compile(r"^([+-])(\d{2}):?(\d{2})$")


class InvalidFortiAnalyzerLogError(ValueError):
    """Le log ne peut pas être converti (sévérité inconnue, date absente ou illisible)."""


@dataclass(frozen=True)
class NormalizedFortiAnalyzerLog:
    identifiant_source: str
    date_evenement: datetime
    type: str
    criticite_source: CriticalityLevel
    donnees_brutes: dict[str, Any]


def normalize_fortianalyzer_log(raw_log: dict[str, Any], fortianalyzer_timezone: ZoneInfo) -> NormalizedFortiAnalyzerLog:
    """Convertit le log. Lève InvalidFortiAnalyzerLogError si un champ indispensable manque ou est illisible."""
    return NormalizedFortiAnalyzerLog(
        identifiant_source=compute_source_identifier(raw_log),
        date_evenement=_read_event_datetime(raw_log, fortianalyzer_timezone),
        type=_read_event_type(raw_log),
        criticite_source=_read_criticality(raw_log),
        donnees_brutes=raw_log,
    )


def compute_source_identifier(raw_log: dict[str, Any]) -> str:
    """Empreinte stable du log (mêmes champs et valeurs ⇒ même identifiant, quel que soit l'ordre des champs).

    Les métadonnées de réception syslog sont exclues : elles décrivent l'arrivée du log, pas le log lui-même.
    """
    fortianalyzer_fields = {key: value for key, value in raw_log.items() if key != SYSLOG_RECEPTION_METADATA_FIELD}
    canonical_log_text = json.dumps(
        fortianalyzer_fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return SOURCE_IDENTIFIER_PREFIX + hashlib.sha256(canonical_log_text.encode("utf-8")).hexdigest()


def _read_criticality(raw_log: dict[str, Any]) -> CriticalityLevel:
    for severity_field in ("severity", "level"):
        severity_value = raw_log.get(severity_field)
        if severity_value is None or str(severity_value).strip() == "":
            continue
        criticality = FORTIANALYZER_SEVERITY_TO_CRITICALITY.get(str(severity_value).strip().lower())
        if criticality is None:
            raise InvalidFortiAnalyzerLogError(f"Sévérité inconnue dans le champ {severity_field} : {severity_value!r}.")
        return criticality
    raise InvalidFortiAnalyzerLogError("Aucune sévérité (champs severity et level absents).")


def _read_event_datetime(raw_log: dict[str, Any], fortianalyzer_timezone: ZoneInfo) -> datetime:
    for timestamp_field in ("eventtime", "itime"):
        if raw_log.get(timestamp_field) not in (None, ""):
            try:
                return _convert_epoch_to_datetime(float(raw_log[timestamp_field]))
            except (TypeError, ValueError, OverflowError, OSError) as conversion_error:
                raise InvalidFortiAnalyzerLogError(f"Champ {timestamp_field} illisible.") from conversion_error
    if raw_log.get("date") and raw_log.get("time"):
        try:
            local_datetime = datetime.strptime(f"{raw_log['date']} {raw_log['time']}", "%Y-%m-%d %H:%M:%S")
        except ValueError as conversion_error:
            raise InvalidFortiAnalyzerLogError("Champs date/time illisibles.") from conversion_error
        return local_datetime.replace(tzinfo=_read_log_timezone(raw_log, fortianalyzer_timezone)).astimezone(UTC)
    raise InvalidFortiAnalyzerLogError("Aucune date (champs eventtime, itime, date/time absents).")


def _read_log_timezone(raw_log: dict[str, Any], fortianalyzer_timezone: ZoneInfo) -> tzinfo:
    """Fuseau du champ `tz` du log s'il est lisible, sinon le fuseau configuré."""
    offset_match = FORTINET_TIMEZONE_OFFSET_REGEX.match(str(raw_log.get("tz") or "").strip())
    if offset_match is None:
        return fortianalyzer_timezone
    sign, hours, minutes = offset_match.groups()
    offset = timedelta(hours=int(hours), minutes=int(minutes))
    return timezone(-offset if sign == "-" else offset)


def _convert_epoch_to_datetime(epoch_value: float) -> datetime:
    """`eventtime` peut être en secondes, millisecondes, microsecondes ou nanosecondes selon la version de FortiOS."""
    while epoch_value > 1e11:  # au-delà, ce ne sont plus des secondes (1e11 s ≈ an 5138)
        epoch_value /= 1000
    return datetime.fromtimestamp(epoch_value, tz=UTC)


def _read_event_type(raw_log: dict[str, Any]) -> str:
    for type_field in ("subtype", "type"):
        type_value = str(raw_log.get(type_field) or "").strip()
        if type_value:
            return type_value[:MAXIMUM_TYPE_LENGTH]
    return "inconnu"
