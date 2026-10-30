"""Boucle de fond : collecte des alertes toutes les LOG_COLLECTION_INTERVAL_SECONDS secondes (0 = désactivée).

Un passage où rien n'est arrivé n'est pas inscrit dans l'historique (sinon une ligne vide toutes les 30 s).

Lancée au démarrage de l'application (`backend/main.py`). Une collecte qui échoue est déjà enregistrée « échouée »
par le service ; une erreur imprévue (base indisponible...) est journalisée et la boucle reprend au tour suivant.
"""

import asyncio
import logging

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from backend.features.log_collection import service
from backend.features.log_collection.schemas import LogCollectionResultRead

collection_scheduler_logger = logging.getLogger(__name__)


async def run_log_collection_periodically(
    database_session_factory: sessionmaker[Session], interval_seconds: float
) -> None:
    """Collecte immédiatement au démarrage, puis toutes les `interval_seconds` secondes, jusqu'à annulation."""

    def collect_with_new_session() -> LogCollectionResultRead | None:
        with database_session_factory() as database_session:
            return service.collect_critical_logs_from_configured_source(
                database_session, is_recorded_when_nothing_received=False
            )

    while True:
        try:
            collection_result = await run_in_threadpool(collect_with_new_session)
            if collection_result is not None:
                collection_scheduler_logger.info(
                    "Collecte %s : %s reçu(s), %s nouveau(x), %s déjà connu(s).",
                    collection_result.statut.value,
                    collection_result.nb_logs_recus,
                    collection_result.nb_logs_inseres,
                    collection_result.nb_logs_ignores,
                )
        except Exception:
            collection_scheduler_logger.exception("Erreur imprévue de la collecte ; nouvel essai au prochain tour.")
        await asyncio.sleep(interval_seconds)
