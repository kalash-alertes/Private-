"""Contexte commun à toutes les pages : menu latéral (avec compteurs), fil d'Ariane, message de confirmation.

Le menu reprend la structure de la maquette (Espace de travail / Investigation / Administration).
L'indicateur de source (`alert_source_indicator`) est affiché sur TOUTES les pages : un analyste ne doit jamais
confondre des alertes inventées (démonstration) avec de vraies alertes.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.core.settings import get_application_settings
from backend.features.dashboard import service as dashboard_service
from backend.features.log_collection import service as log_collection_service
from web_interface.page_notices import find_page_notice_message

APPLICATION_NAME = "FAnalyzer IR"


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    icon_name: str
    url: str


@dataclass(frozen=True)
class AlertSourceIndicator:
    """Source des alertes, telle qu'affichée en haut de chaque page.

    `mode` (classe CSS) : `demo` (alertes inventées), `live` (réception syslog à l'écoute), `live-inactive` (mode réel
    mais rien n'écoute : port occupé, réglage invalide). Seul `demo` affiche en plus le bandeau rayé.
    """

    mode: str
    badge_label: str
    description: str


@dataclass(frozen=True)
class NavigationGroup:
    label: str
    items: list[NavigationItem]


NAVIGATION_GROUPS = [
    NavigationGroup(
        "ESPACE DE TRAVAIL",
        [
            NavigationItem("tableau_de_bord", "Tableau de bord", "layout_dashboard", "/"),
            NavigationItem("incidents", "Incidents", "shield_alert", "/incidents"),
            NavigationItem("alertes", "Alertes", "bell", "/alertes"),
            NavigationItem("journaux", "Journaux", "file_search", "/journaux"),
        ],
    ),
    NavigationGroup("INVESTIGATION", [NavigationItem("playbooks", "Playbooks", "clipboard_list", "/parametres/playbooks")]),
    NavigationGroup("ADMINISTRATION", [NavigationItem("parametres", "Paramètres", "settings", "/parametres")]),
]


def build_application_layout_context(
    database_session: Session,
    active_navigation_key: str,
    page_title: str,
    page_description: str,
    notice_key: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Retourne les variables utilisées par `layouts/application_layout.html` (menu, compteurs, titre, messages)."""
    dashboard = dashboard_service.build_dashboard(database_session, activity_day_count=1)
    return {
        "application_name": APPLICATION_NAME,
        "navigation_groups": NAVIGATION_GROUPS,
        "active_navigation_key": active_navigation_key,
        "navigation_counts": {
            "incidents": dashboard.nombre_incidents_ouverts,
            "alertes": dashboard.nombre_alertes_a_traiter,
        },
        "is_demo_mode": get_application_settings().app_is_in_demo,
        "alert_source_indicator": build_alert_source_indicator(),
        "page_title": page_title,
        "page_description": page_description,
        "notice_message": find_page_notice_message(notice_key),
        "error_message": error_message,
    }


def build_alert_source_indicator() -> AlertSourceIndicator:
    """Décrit la source des alertes (démonstration, réception active ou inactive). Sans accès à la base."""
    configuration = log_collection_service.describe_collection_configuration(get_application_settings())
    if configuration.est_en_mode_demo:
        return AlertSourceIndicator(
            "demo", "MODE DÉMO", "Alertes inventées (APP_IS_IN_DEMO=true) : rien ne vient de FortiAnalyzer."
        )
    if configuration.est_a_l_ecoute:
        return AlertSourceIndicator(
            "live", "EN DIRECT", f"Alertes réelles reçues de FortiAnalyzer ({configuration.source})."
        )
    return AlertSourceIndicator(
        "live-inactive",
        "SYSLOG INACTIF",
        "Mode réel, mais aucune alerte ne peut arriver : la réception syslog n'écoute pas (voir Journaux).",
    )
