"""Page « Logs bruts » (`/logs-bruts`) : les messages syslog tels qu'envoyés par FortiAnalyzer, en direct, chacun
dépliable pour voir tous ses champs et son texte d'origine (présentation inspirée de Wazuh).

`/logs-bruts/nouveaux` renvoie un fragment HTML (nouveaux messages + bilan) que le script
`static/js/raw_syslog_feed.js` insère toutes les quelques secondes ; sans JavaScript, la page reste utilisable
(rechargement manuel). Les fragments sont rendus par Jinja2 : tout le texte des logs est échappé.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.settings import get_application_settings
from backend.features.raw_syslog_feed import service as raw_syslog_feed_service
from backend.features.raw_syslog_feed.schemas import (
    MAXIMUM_SEARCH_TEXT_LENGTH,
    CollectionOutcomeFilter,
    RawSyslogFeedFilters,
)
from web_interface.application_layout import build_application_layout_context
from web_interface.template_rendering import page_templates, render_page

raw_syslog_feed_page_router = APIRouter()

MESSAGES_SHOWN_ON_PAGE_LOAD = 200
COLLECTION_OUTCOME_LABELS = {
    CollectionOutcomeFilter.ALL: "Enregistrés et écartés",
    CollectionOutcomeFilter.STORED: "Enregistrés en base seulement",
    CollectionOutcomeFilter.DISCARDED: "Écartés seulement",
}


def _build_filters(criticite: str | None, enregistrement: str | None, recherche: str | None, apres: int) -> RawSyslogFeedFilters:
    """Les formulaires envoient « » pour « tous » : une valeur vide ou inconnue revient au filtre neutre."""
    criticality_values = {level.value for level in CriticalityLevel}
    outcome_values = {outcome.value for outcome in CollectionOutcomeFilter}
    return RawSyslogFeedFilters(
        criticite=CriticalityLevel(criticite) if criticite in criticality_values else None,
        enregistrement=CollectionOutcomeFilter(enregistrement) if enregistrement in outcome_values else CollectionOutcomeFilter.ALL,
        recherche=(recherche or "").strip()[:MAXIMUM_SEARCH_TEXT_LENGTH] or None,
        apres=apres,
        limite=MESSAGES_SHOWN_ON_PAGE_LOAD,
    )


def _build_filter_query(filters: RawSyslogFeedFilters) -> str:
    """Paramètres de filtre à répéter dans les appels du script (sans `apres`, qu'il gère lui-même)."""
    query_values = {}
    if filters.criticite:
        query_values["criticite"] = filters.criticite.value
    if filters.enregistrement != CollectionOutcomeFilter.ALL:
        query_values["enregistrement"] = filters.enregistrement.value
    if filters.recherche:
        query_values["recherche"] = filters.recherche
    return urlencode(query_values)


@raw_syslog_feed_page_router.get("/logs-bruts", response_class=HTMLResponse)
def show_raw_syslog_feed_page(
    request: Request,
    database_session: Annotated[Session, Depends(get_database_session)],
    criticite: str | None = None,
    enregistrement: str | None = None,
    recherche: str | None = None,
) -> HTMLResponse:
    """Derniers messages reçus (plus récents d'abord) et répartition par niveau depuis le démarrage."""
    filters = _build_filters(criticite, enregistrement, recherche, apres=0)
    feed = raw_syslog_feed_service.read_raw_syslog_feed(get_application_settings(), filters)
    return render_page(
        request,
        "raw_syslog_feed.html",
        {
            **build_application_layout_context(
                database_session,
                "logs_bruts",
                "Logs bruts",
                "Ce que FortiAnalyzer envoie réellement, en direct, avant le filtre de sévérité. Cliquer sur un log pour voir tous ses champs.",
            ),
            "feed": feed,
            "filters": filters,
            "filter_query": _build_filter_query(filters),
            "collection_outcome_labels": list(COLLECTION_OUTCOME_LABELS.items()),
        },
    )


@raw_syslog_feed_page_router.get("/logs-bruts/nouveaux", response_class=HTMLResponse)
def show_new_raw_syslog_messages(
    request: Request,
    apres: Annotated[int, Query(ge=0)] = 0,
    criticite: str | None = None,
    enregistrement: str | None = None,
    recherche: str | None = None,
) -> HTMLResponse:
    """Fragment pour le rafraîchissement automatique : messages arrivés après `apres` et bilan à jour."""
    filters = _build_filters(criticite, enregistrement, recherche, apres=apres)
    feed = raw_syslog_feed_service.read_raw_syslog_feed(get_application_settings(), filters)
    return page_templates.TemplateResponse(
        request=request, name="partials/raw_syslog_feed_update.html", context={"feed": feed}
    )
