"""Conversion d'un log FortiAnalyzer brut en log de l'application (sévérité, date, type, identifiant de déduplication).

Règles (PROVISOIRES : à confirmer sur les vrais logs du FortiAnalyzer de l'équipe, cf. explain_project.md section 15) :

- **Sévérité** : le champ `severity` (logs d'attaque IPS : critical, high, medium, low, info) est prioritaire ; à
  défaut, le champ `level` (syslog : emergency → debug). Correspondance :
  emergency, alert, critical → critique · error, high → haute · warning, medium → moyenne · notice, low → faible ·
  information, info, debug → information. Une valeur inconnue rend le log invalide (il est compté, pas enregistré).
- **Date de l'événement** : `eventtime` (horodatage de l'équipement, en s, ms, µs ou ns selon la version), sinon
  `itime` (réception par FortiAnalyzer, en secondes), sinon `date` + `time` dans le fuseau FORTIANALYZER_TIMEZONE.
- **Type** (sert aussi de catégorie d'incident, donc au choix du playbook) : `subtype` (ips, virus, system...), sinon
  `type`, sinon le type de log recherché.
- **Identifiant de déduplication** : FortiAnalyzer ne fournit pas d'identifiant unique garanti entre équipements ; on
  calcule une empreinte SHA-256 du log complet (champs triés). Le même log relu à la collecte suivante (périodes qui
  se chevauchent) donne la même empreinte : il n'est pas recréé. Si FortiAnalyzer ajoute un champ variable à chaque
  lecture, cette règle devra être revue (exclure ce champ de l'empreinte).
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.core.criticality import CriticalityLevel

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


class InvalidFortiAnalyzerLogError(ValueError):
    """Le log ne peut pas être converti (sévérité inconnue, date absente ou illisible)."""


@dataclass(frozen=True)
class NormalizedFortiAnalyzerLog:
    identifiant_source: str
    date_evenement: datetime
    type: str
    criticite_source: CriticalityLevel
    donnees_brutes: dict[str, Any]


def normalize_fortianalyzer_log(
    raw_log: dict[str, Any], searched_log_type: str | None, fortianalyzer_timezone: ZoneInfo
) -> NormalizedFortiAnalyzerLog:
    """Convertit le log. Lève InvalidFortiAnalyzerLogError si un champ indispensable manque ou est illisible."""
    return NormalizedFortiAnalyzerLog(
        identifiant_source=compute_source_identifier(raw_log),
        date_evenement=_read_event_datetime(raw_log, fortianalyzer_timezone),
        type=_read_event_type(raw_log, searched_log_type),
        criticite_source=_read_criticality(raw_log),
        donnees_brutes=raw_log,
    )


def compute_source_identifier(raw_log: dict[str, Any]) -> str:
    """Empreinte stable du log (mêmes champs et valeurs ⇒ même identifiant, quel que soit l'ordre des champs)."""
    canonical_log_text = json.dumps(raw_log, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
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
        return local_datetime.replace(tzinfo=fortianalyzer_timezone).astimezone(UTC)
    raise InvalidFortiAnalyzerLogError("Aucune date (champs eventtime, itime, date/time absents).")


def _convert_epoch_to_datetime(epoch_value: float) -> datetime:
    """`eventtime` peut être en secondes, millisecondes, microsecondes ou nanosecondes selon la version de FortiOS."""
    while epoch_value > 1e11:  # au-delà, ce ne sont plus des secondes (1e11 s ≈ an 5138)
        epoch_value /= 1000
    return datetime.fromtimestamp(epoch_value, tz=UTC)


def _read_event_type(raw_log: dict[str, Any], searched_log_type: str | None) -> str:
    for type_field in ("subtype", "type"):
        type_value = str(raw_log.get(type_field) or "").strip()
        if type_value:
            return type_value[:MAXIMUM_TYPE_LENGTH]
    return (searched_log_type or "inconnu")[:MAXIMUM_TYPE_LENGTH]
