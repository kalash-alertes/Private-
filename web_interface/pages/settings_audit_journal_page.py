"""Paramètres > Journal d'audit (`/parametres/journal-audit`) : événements du système, les plus récents d'abord.

Lecture seule. Les connexions (réussies / échouées) y apparaîtront dès que l'authentification sera en place.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.database import get_database_session
from backend.core.pagination import PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import AuditEventListFilters
from web_interface.application_layout import build_application_layout_context
from web_interface.display_formatting import AUDIT_EVENT_TYPE_LABELS
from web_interface.template_rendering import render_page

settings_audit_journal_page_router = APIRouter()

AUDIT_EVENTS_PER_PAGE = 50

# Lien vers la page d'une ressource citée dans le journal (les playbooks supprimés n'ont plus de page : pas de lien).
RESOURCE_URL_TEMPLATES = {"incident": "/incidents/{identifier}"}


@settings_audit_journal_page_router.get("/parametres/journal-audit", response_class=HTMLResponse)
def show_audit_journal_page(
    request: Request,
    database_session: Annotated[Session, Depends(get_database_session)],
    type_evenement: AuditEventType | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HTMLResponse:
    """Journal paginé, filtrable par type d'événement."""
    audit_events_page = audit_journal_service.list_audit_events(
        database_session,
        AuditEventListFilters(type_evenement=type_evenement),
        PaginationParameters(limit=AUDIT_EVENTS_PER_PAGE, offset=offset),
    )
    return render_page(
        request,
        "settings_audit_journal.html",
        {
            **build_application_layout_context(
                database_session,
                "parametres",
                "Paramètres",
                "Journal d'audit : ce qui s'est passé dans l'application, par qui et quand.",
            ),
            "active_settings_section": "journal_audit",
            "audit_events_page": audit_events_page,
            "audit_event_types": list(AUDIT_EVENT_TYPE_LABELS.items()),
            "selected_event_type": type_evenement,
            "filter_query": urlencode({"type_evenement": type_evenement.value} if type_evenement else {}),
            "resource_urls_by_event_id": {
                audit_event.id: RESOURCE_URL_TEMPLATES[audit_event.type_ressource].format(
                    identifier=audit_event.identifiant_ressource
                )
                for audit_event in audit_events_page.items
                if audit_event.type_ressource in RESOURCE_URL_TEMPLATES and audit_event.identifiant_ressource
            },
        },
    )
