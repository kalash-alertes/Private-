"""Charge des données de DÉMONSTRATION SYNTHÉTIQUES pour voir l'interface remplie (base de développement uniquement).

Usage (base désignée par DATABASE_URL, déjà migrée avec `alembic upgrade head`) :
    python -m scripts.load_synthetic_demo_data

Tout est inventé : identifiants préfixés `SYNTHETIQUE-DEMO-`, playbooks dont la source indique qu'ils ne sont PAS
des procédures réelles. Ne jamais lancer ce script sur une base de production. Il passe par les services métier :
les règles (déduplication, audit, références) s'appliquent comme en usage réel. Relancé, il ne recrée pas les logs.
"""

from datetime import UTC, datetime, timedelta

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session_factory
from backend.core.domain_errors import ResourceConflictError
from backend.core.settings import get_application_settings
from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.schemas import FinishedImportRunStatus, ImportRunFinishedOutcome
from backend.features.incidents import incident_playbook_progress
from backend.features.incidents import service as incidents_service
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCreationRequest,
    IncidentPlaybookStepCompletionRequest,
    IncidentStatusChangeRequest,
)
from backend.features.playbooks import service as playbooks_service
from backend.features.playbooks.schemas import PlaybookStepWriteRequest, PlaybookWriteRequest
from backend.features.source_logs import service as source_logs_service
from backend.features.source_logs.schemas import NewSourceLogData

DEMO_SOURCE_IDENTIFIER_PREFIX = "SYNTHETIQUE-DEMO-"
DEMO_PLAYBOOK_SOURCE = "DONNÉE DE DÉMONSTRATION SYNTHÉTIQUE — ne constitue pas une procédure validée"

# (suffixe, type d'événement, criticité, ancienneté en heures, statut final, responsable)
DEMO_ALERTS = [
    ("001", "intrusion", CriticalityLevel.CRITICAL, 3, "en_cours", "analyste.n1"),
    ("002", "intrusion", CriticalityLevel.HIGH, 30, "nouveau", None),
    ("003", "malware", CriticalityLevel.CRITICAL, 0.5, "nouveau", None),
    ("004", "phishing", CriticalityLevel.MEDIUM, 50, "en_attente", "analyste.n2"),
    ("005", "malware", CriticalityLevel.HIGH, 70, "resolu", "analyste.n1"),
    ("006", "phishing", CriticalityLevel.LOW, 100, "cloture", "analyste.n2"),
    ("007", "intrusion", CriticalityLevel.MEDIUM, 20, None, None),
    ("008", "scan_reseau", CriticalityLevel.LOW, 10, None, None),
]

DEMO_PLAYBOOKS = [
    ("Investigation d'une intrusion (démo)", "intrusion", [
        "Identifier les adresses source et destination", "Vérifier les journaux FortiGate associés",
        "Isoler le poste si la compromission est confirmée", "Documenter les constats",
    ]),
    ("Analyse d'un malware (démo)", "malware", [
        "Récupérer l'empreinte du fichier", "Rechercher les autres postes touchés", "Valider la remédiation",
    ]),
    ("Traitement d'un phishing (démo)", "phishing", [
        "Identifier les destinataires", "Bloquer l'expéditeur", "Informer les utilisateurs concernés",
    ]),
]


def load_synthetic_demo_data() -> None:
    """Crée playbooks, import, alertes et incidents de démonstration (idempotent pour les alertes)."""
    with get_database_session_factory()() as database_session:
        for playbook_name, category, step_titles in DEMO_PLAYBOOKS:
            try:
                playbooks_service.create_playbook(
                    database_session,
                    PlaybookWriteRequest(
                        nom=playbook_name,
                        categorie=category,
                        source=DEMO_PLAYBOOK_SOURCE,
                        etapes=[PlaybookStepWriteRequest(titre=step_title) for step_title in step_titles],
                    ),
                )
            except ResourceConflictError:
                database_session.rollback()  # déjà chargé lors d'une exécution précédente

        import_run = import_runs_service.start_import_run(database_session)
        inserted_alert_count = 0
        current_time = datetime.now(UTC)
        for suffix, event_type, criticality, age_in_hours, final_status, assignee in DEMO_ALERTS:
            storage_result = source_logs_service.store_source_log_if_new(
                database_session,
                NewSourceLogData(
                    identifiant_source=f"{DEMO_SOURCE_IDENTIFIER_PREFIX}{suffix}",
                    date_evenement=current_time - timedelta(hours=age_in_hours),
                    type=event_type,
                    criticite_source=criticality,
                    donnees_brutes={"origine": "donnees_de_demonstration_synthetiques"},
                    execution_import_id=import_run.id,
                ),
            )
            if not storage_result.was_inserted:
                continue
            inserted_alert_count += 1
            if final_status is None:
                continue  # alerte laissée « à traiter »
            incident = incidents_service.create_incident_from_source_log(
                database_session, IncidentCreationRequest(log_id=storage_result.source_log_id)
            )
            if assignee:
                incidents_service.change_incident_assignment(
                    database_session, incident.id, IncidentAssignmentRequest(assigne_a=assignee)
                )
            playbook_view = incident_playbook_progress.fetch_incident_playbook(database_session, incident.id)
            if playbook_view.playbook and final_status != "nouveau":
                incident_playbook_progress.change_incident_playbook_step_completion(
                    database_session,
                    incident.id,
                    playbook_view.playbook.etapes[0].id,
                    IncidentPlaybookStepCompletionRequest(realisee=True, realisee_par=assignee),
                )
            if final_status != "nouveau":
                incidents_service.change_incident_status(
                    database_session, incident.id, IncidentStatusChangeRequest(statut=final_status)
                )

        import_runs_service.finish_import_run(
            database_session,
            import_run.id,
            ImportRunFinishedOutcome(
                statut=FinishedImportRunStatus.SUCCEEDED,
                nb_logs_recus=len(DEMO_ALERTS),
                nb_logs_inseres=inserted_alert_count,
                nb_logs_ignores=len(DEMO_ALERTS) - inserted_alert_count,
            ),
        )
    print(f"Données de démonstration chargées ({inserted_alert_count} nouvelle(s) alerte(s)).")


if __name__ == "__main__":
    if get_application_settings().application_environment == "production":
        raise SystemExit("Refusé : ce script ne doit jamais être lancé sur une base de production.")
    if not get_application_settings().app_is_in_demo:
        raise SystemExit("Refusé : APP_IS_IN_DEMO=false (données réelles FortiAnalyzer) ; pas de données inventées.")
    load_synthetic_demo_data()
