"""Route HTTP du flux des logs bruts. Aucune logique métier ici : tout passe par `service.py`."""

from typing import Annotated

from fastapi import APIRouter, Query

from backend.core.settings import get_application_settings
from backend.features.raw_syslog_feed import service
from backend.features.raw_syslog_feed.schemas import RawSyslogFeedFilters, RawSyslogFeedRead

raw_syslog_feed_router = APIRouter(prefix="/logs-bruts", tags=["logs bruts"])


@raw_syslog_feed_router.get("", response_model=RawSyslogFeedRead)
def read_raw_syslog_feed(filters: Annotated[RawSyslogFeedFilters, Query()]) -> RawSyslogFeedRead:
    """Derniers messages syslog reçus, tels quels (avant le filtre de sévérité), plus récents d'abord, avec le bilan
    par niveau. Interroger ensuite avec `apres=<dernier_numero>` pour ne recevoir que les nouveaux."""
    return service.read_raw_syslog_feed(get_application_settings(), filters)
