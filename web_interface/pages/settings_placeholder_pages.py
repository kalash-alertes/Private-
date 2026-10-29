"""Paramètres > Clients et Paramètres > Utilisateurs : sections prévues mais jugées non prioritaires par l'équipe.

Elles existent dans la navigation pour que la structure des Paramètres soit complète ; leur contenu viendra plus tard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from web_interface.application_layout import build_application_layout_context
from web_interface.template_rendering import render_page

settings_placeholder_pages_router = APIRouter()

PLACEHOLDER_SECTIONS = {
    "clients": (
        "Clients",
        "La gestion des clients (organisations suivies) n'est pas encore développée.",
    ),
    "utilisateurs": (
        "Utilisateurs",
        "La gestion des comptes et la connexion des utilisateurs ne sont pas encore développées. En attendant, le "
        "responsable d'un incident est un nom saisi librement.",
    ),
}


@settings_placeholder_pages_router.get("/parametres/clients", response_class=HTMLResponse)
def show_clients_settings_page(
    request: Request, database_session: Annotated[Session, Depends(get_database_session)]
) -> HTMLResponse:
    return _render_placeholder_section(request, database_session, "clients")


@settings_placeholder_pages_router.get("/parametres/utilisateurs", response_class=HTMLResponse)
def show_users_settings_page(
    request: Request, database_session: Annotated[Session, Depends(get_database_session)]
) -> HTMLResponse:
    return _render_placeholder_section(request, database_session, "utilisateurs")


def _render_placeholder_section(request: Request, database_session: Session, section_key: str) -> HTMLResponse:
    section_title, section_explanation = PLACEHOLDER_SECTIONS[section_key]
    return render_page(
        request,
        "settings_placeholder.html",
        {
            **build_application_layout_context(
                database_session, "parametres", "Paramètres", f"{section_title} : section prévue."
            ),
            "active_settings_section": section_key,
            "section_title": section_title,
            "section_explanation": section_explanation,
        },
    )
