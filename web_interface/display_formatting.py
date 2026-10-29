"""Mise en forme des valeurs métier pour l'affichage : libellés français, classes CSS des pastilles, dates, durées.

Les valeurs stockées (`haute`, `en_cours`...) ne sont jamais affichées brutes : tout passe par ces fonctions, exposées
aux gabarits comme filtres Jinja (voir `template_rendering.py`).
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.core.criticality import CriticalityLevel
from backend.features.audit_journal.models import AuditEventType
from backend.features.import_runs.models import ImportRunStatus
from backend.features.incidents.models import IncidentStatus

# Fuseau d'affichage des dates (elles sont stockées en UTC). Repli sur UTC si la base des fuseaux est absente.
try:
    DISPLAY_TIMEZONE = ZoneInfo("Europe/Paris")
except ZoneInfoNotFoundError:
    DISPLAY_TIMEZONE = UTC

# De la plus grave à la moins grave : ordre d'affichage partout dans l'interface.
CRITICALITY_LEVELS_FROM_MOST_SEVERE = [
    CriticalityLevel.CRITICAL,
    CriticalityLevel.HIGH,
    CriticalityLevel.MEDIUM,
    CriticalityLevel.LOW,
    CriticalityLevel.INFORMATION,
]

CRITICALITY_LABELS = {
    CriticalityLevel.CRITICAL: "Critique",
    CriticalityLevel.HIGH: "Haute",
    CriticalityLevel.MEDIUM: "Moyenne",
    CriticalityLevel.LOW: "Faible",
    CriticalityLevel.INFORMATION: "Information",
}
# Suffixe des classes CSS `severity-*` et `dot-*` (components.css).
CRITICALITY_CSS_SUFFIXES = {
    CriticalityLevel.CRITICAL: "critical",
    CriticalityLevel.HIGH: "high",
    CriticalityLevel.MEDIUM: "medium",
    CriticalityLevel.LOW: "low",
    CriticalityLevel.INFORMATION: "info",
}

INCIDENT_STATUS_LABELS = {
    IncidentStatus.NEW: "Nouveau",
    IncidentStatus.IN_PROGRESS: "En cours",
    IncidentStatus.ON_HOLD: "En attente",
    IncidentStatus.RESOLVED: "Résolu",
    IncidentStatus.CLOSED: "Clôturé",
}
INCIDENT_STATUS_CSS_SUFFIXES = {
    IncidentStatus.NEW: "new",
    IncidentStatus.IN_PROGRESS: "progress",
    IncidentStatus.ON_HOLD: "review",
    IncidentStatus.RESOLVED: "closed",
    IncidentStatus.CLOSED: "archived",
}

IMPORT_RUN_STATUS_LABELS = {
    ImportRunStatus.IN_PROGRESS: "En cours",
    ImportRunStatus.SUCCEEDED: "Réussie",
    ImportRunStatus.PARTIALLY_SUCCEEDED: "Partielle",
    ImportRunStatus.FAILED: "Échouée",
}
IMPORT_RUN_STATUS_CSS_SUFFIXES = {
    ImportRunStatus.IN_PROGRESS: "progress",
    ImportRunStatus.SUCCEEDED: "closed",
    ImportRunStatus.PARTIALLY_SUCCEEDED: "review",
    ImportRunStatus.FAILED: "failed",
}

AUDIT_EVENT_TYPE_LABELS = {
    AuditEventType.LOGIN_SUCCEEDED: "Connexion réussie",
    AuditEventType.LOGIN_FAILED: "Connexion échouée",
    AuditEventType.LOGOUT: "Déconnexion",
    AuditEventType.INCIDENT_CREATED: "Incident créé",
    AuditEventType.INCIDENT_UPDATED: "Incident modifié",
    AuditEventType.INCIDENT_ESCALATED: "Incident escaladé",
    AuditEventType.PLAYBOOK_CREATED: "Playbook créé",
    AuditEventType.PLAYBOOK_UPDATED: "Playbook modifié",
    AuditEventType.PLAYBOOK_DELETED: "Playbook supprimé",
    AuditEventType.SETTINGS_UPDATED: "Paramètres modifiés",
}
# Les échecs de connexion et escalades ressortent visuellement dans le journal.
AUDIT_EVENT_TYPE_CSS_SUFFIXES = {
    AuditEventType.LOGIN_FAILED: "failed",
    AuditEventType.INCIDENT_ESCALATED: "review",
    AuditEventType.LOGIN_SUCCEEDED: "closed",
}

FRENCH_SHORT_WEEKDAY_NAMES = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def format_criticality_label(criticality: str | None) -> str:
    return CRITICALITY_LABELS.get(CriticalityLevel(criticality), criticality) if criticality else "—"


def format_criticality_css_suffix(criticality: str) -> str:
    return CRITICALITY_CSS_SUFFIXES[CriticalityLevel(criticality)]


def format_incident_status_label(status: str) -> str:
    return INCIDENT_STATUS_LABELS[IncidentStatus(status)]


def format_incident_status_css_suffix(status: str) -> str:
    return INCIDENT_STATUS_CSS_SUFFIXES[IncidentStatus(status)]


def format_import_run_status_label(status: str) -> str:
    return IMPORT_RUN_STATUS_LABELS[ImportRunStatus(status)]


def format_import_run_status_css_suffix(status: str) -> str:
    return IMPORT_RUN_STATUS_CSS_SUFFIXES[ImportRunStatus(status)]


def format_audit_event_type_label(event_type: str) -> str:
    return AUDIT_EVENT_TYPE_LABELS[AuditEventType(event_type)]


def format_audit_event_type_css_suffix(event_type: str) -> str:
    return AUDIT_EVENT_TYPE_CSS_SUFFIXES.get(AuditEventType(event_type), "progress")


def format_datetime_for_display(value: datetime | None) -> str:
    """`29/10/2026 14:05` dans le fuseau d'affichage ; « — » si absent."""
    if value is None:
        return "—"
    aware_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware_value.astimezone(DISPLAY_TIMEZONE).strftime("%d/%m/%Y %H:%M")


def format_duration_in_minutes(minutes: float | int | None) -> str:
    """`45 min`, `3 h 05`, `2 j 4 h` ; « — » si absent."""
    if minutes is None:
        return "—"
    total_minutes = int(round(minutes))
    if total_minutes < 60:
        return f"{total_minutes} min"
    days, remaining_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes_part = divmod(remaining_minutes, 60)
    if days:
        return f"{days} j {hours} h" if hours else f"{days} j"
    return f"{hours} h {minutes_part:02d}" if minutes_part else f"{hours} h"


def format_short_day_label(day) -> str:
    """`lun. 27` : étiquette d'un jour sur l'axe du graphique d'activité."""
    return f"{FRENCH_SHORT_WEEKDAY_NAMES[day.weekday()]} {day.day}"


def build_person_initials(person_name: str | None) -> str:
    """Initiales affichées dans la pastille du responsable (`jean.dupont` → `JD`) ; « — » si non assigné."""
    if not person_name:
        return "—"
    name_parts = [part for part in person_name.replace(".", " ").replace("_", " ").split() if part]
    return "".join(part[0] for part in name_parts[:2]).upper() or "—"


def format_number(value: int | float | None) -> str:
    """Nombre avec séparateur de milliers français (espace insécable fine)."""
    if value is None:
        return "—"
    return f"{value:,}".replace(",", " ")
