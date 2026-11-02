"""Données de test SYNTHÉTIQUES.

Ces données sont inventées pour tester les services internes. Elles ne reproduisent PAS le format de l'API
FortiAnalyzer (non encore étudiée) et ne prouvent en rien qu'une collecte réelle fonctionne.
Tous les identifiants source commencent par `SYNTHETIQUE-` pour être reconnaissables partout.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.features.import_runs import service as import_runs_service
from backend.features.playbooks.schemas import PlaybookStepWriteRequest, PlaybookWriteRequest
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import NewSourceLogData, SourceLogStorageResult

SYNTHETIC_SOURCE_IDENTIFIER_PREFIX = "SYNTHETIQUE-"
SYNTHETIC_EVENT_DATE = datetime(2026, 10, 1, 8, 30, tzinfo=UTC)


def build_synthetic_new_source_log(
    execution_import_id: UUID,
    identifier_suffix: str = "0001",
    criticite_source: CriticalityLevel = CriticalityLevel.CRITICAL,
    date_evenement: datetime = SYNTHETIC_EVENT_DATE,
    event_type: str = "synthetique_intrusion",
) -> NewSourceLogData:
    """Construit un log normalisé synthétique, rattaché à l'exécution donnée."""
    return NewSourceLogData(
        identifiant_source=f"{SYNTHETIC_SOURCE_IDENTIFIER_PREFIX}{identifier_suffix}",
        date_evenement=date_evenement,
        type=event_type,
        criticite_source=criticite_source,
        donnees_brutes={"origine": "donnees_synthetiques_de_test", "suffixe": identifier_suffix},
        execution_import_id=execution_import_id,
    )


def store_synthetic_source_log(
    database_session: Session,
    identifier_suffix: str = "0001",
    criticite_source: CriticalityLevel = CriticalityLevel.CRITICAL,
    **new_source_log_overrides,
) -> SourceLogStorageResult:
    """Démarre une exécution synthétique et y enregistre un log synthétique (via les vrais services)."""
    import_run = import_runs_service.start_import_run(database_session)
    return source_logs_service.store_source_log_if_new(
        database_session,
        build_synthetic_new_source_log(
            import_run.id, identifier_suffix, criticite_source=criticite_source, **new_source_log_overrides
        ),
    )


def build_synthetic_playbook_request(
    categorie: str | None = "synthetique_intrusion", nom: str = "Playbook synthétique", step_count: int = 3
) -> PlaybookWriteRequest:
    """Playbook synthétique (la source indique clairement qu'il s'agit d'une donnée de test, pas d'une procédure)."""
    return PlaybookWriteRequest(
        nom=nom,
        categorie=categorie,
        source="DONNÉE DE TEST SYNTHÉTIQUE — aucune procédure réelle",
        etapes=[PlaybookStepWriteRequest(titre=f"Étape synthétique {index}") for index in range(1, step_count + 1)],
    )
