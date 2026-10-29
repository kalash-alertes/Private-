"""Contexte commun à toutes les pages : menu latéral (avec compteurs), fil d'Ariane, message de confirmation.

Le menu reprend la structure de la maquette (Espace de travail / Investigation / Administration).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.features.dashboard import service as dashboard_service
from web_interface.page_notices import find_page_notice_message

APPLICATION_NAME = "FAnalyzer IR"


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    icon_name: str
    url: str


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
        "page_title": page_title,
        "page_description": page_description,
        "notice_message": find_page_notice_message(notice_key),
        "error_message": error_message,
    }
