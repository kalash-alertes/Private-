"""Règles métier du cycle de vie d'un incident.

Règles appliquées (les règles PROVISOIRES sont à confirmer, cf. docs/technical/incidents.md) :
- un incident naît d'un log existant ; un log ne donne au plus qu'un incident (V1) ;
- il reçoit une référence lisible séquentielle (INC-000001) ; titre et catégorie sont déduits du type du log
  s'ils ne sont pas fournis ; le playbook de sa catégorie (s'il existe) lui est attribué automatiquement ;
- `criticite_actuelle` est initialisée avec la criticité source du log, qui n'est jamais modifiée ici ;
- PROVISOIRE : toutes les transitions de statut sont autorisées (aucun graphe de transitions n'est encore défini) ;
- passer à `cloture` fixe `closed_at` ; quitter `cloture` (réouverture) remet `closed_at` à NULL.
  Sans table d'historique, la date de la clôture précédente est alors perdue ;
- devenir « traité » (résolu ou clôturé) fixe `traite_le` ; redevenir ouvert le remet à NULL ;
- PROVISOIRE : un incident clôturé est en lecture seule (criticité, faux positif, attribution, titre, catégorie,
  playbook, étapes) : il faut le rouvrir pour le modifier. Objectif : que le contenu d'un incident clôturé (base du
  futur rapport) ne change pas en silence ;
- une demande qui ne change rien ne modifie pas `updated_at` et n'écrit rien dans le journal d'audit ;
- chaque changement effectif est tracé dans le journal d'audit, dans la même transaction.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.audit_journal.models import AuditEventType
from backend.features.incidents import repository
from backend.features.incidents.incident_audit_trail import record_incident_audit_event
from backend.features.incidents.incident_views import build_incident_detail, build_incident_list_items
from backend.features.incidents.models import (
    HANDLED_INCIDENT_STATUSES,
    OPEN_INCIDENT_STATUSES,
    Incident,
    IncidentStatus,
)
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCategoryChangeRequest,
    IncidentCreationRequest,
    IncidentCriticalityChangeRequest,
    IncidentDetailRead,
    IncidentFalsePositiveQualificationRequest,
    IncidentListFilters,
    IncidentListItemRead,
    IncidentListView,
    IncidentPlaybookAssignmentRequest,
    IncidentStatusChangeRequest,
    IncidentTitleChangeRequest,
)
from backend.features.playbooks import service as playbooks_service
from backend.features.source_logs import service as source_logs_service

STATUSES_BY_LIST_VIEW = {
    IncidentListView.IN_PROGRESS: OPEN_INCIDENT_STATUSES,
    IncidentListView.HANDLED: HANDLED_INCIDENT_STATUSES,
}


def create_incident_from_source_log(
    database_session: Session, creation_request: IncidentCreationRequest
) -> IncidentDetailRead:
    """Crée un incident `nouveau` à partir d'un log, avec la criticité source comme criticité actuelle.

    Lève ResourceNotFoundError si le log n'existe pas, ResourceConflictError si le log a déjà un incident
    (y compris lorsque deux créations simultanées visent le même log).
    """
    log_id = creation_request.log_id
    source_log = source_logs_service.fetch_source_log_metadata(database_session, log_id)
    categorie = creation_request.categorie or source_log.type
    incident = repository.insert_incident_unless_log_already_has_one(
        database_session,
        {
            "log_id": log_id,
            "criticite_actuelle": source_log.criticite_source.value,
            "titre": creation_request.titre or f"Alerte {source_log.type}",
            "categorie": categorie,
            "playbook_id": playbooks_service.find_playbook_id_for_category(database_session, categorie),
        },
    )
    if incident is None:
        existing_incident = repository.fetch_incident_by_log_id(database_session, log_id)
        raise ResourceConflictError(
            f"Le log {log_id} a déjà un incident ({existing_incident.id if existing_incident else 'inconnu'})."
        )
    record_incident_audit_event(
        database_session, incident, AuditEventType.INCIDENT_CREATED, f"incident créé à partir du log {log_id}."
    )
    database_session.commit()
    database_session.refresh(incident)
    return build_incident_detail(database_session, incident)


def fetch_incident_detail(database_session: Session, incident_id: UUID) -> IncidentDetailRead:
    """Retourne le détail d'un incident. Lève ResourceNotFoundError s'il n'existe pas."""
    return build_incident_detail(database_session, fetch_existing_incident(database_session, incident_id))


def list_incidents(
    database_session: Session, filters: IncidentListFilters, pagination: PaginationParameters
) -> PaginatedResponse[IncidentListItemRead]:
    """Retourne une page d'incidents, les plus récents d'abord. `vue` : onglet « en_cours » ou « traites »."""
    filter_values = {
        "statut": filters.statut.value if filters.statut else None,
        "statuts": [status.value for status in STATUSES_BY_LIST_VIEW[filters.vue]] if filters.vue else None,
        "recherche": filters.recherche.strip() if filters.recherche else None,
        "criticite_actuelle": filters.criticite_actuelle.value if filters.criticite_actuelle else None,
        "faux_positif": filters.faux_positif,
        "assigne_a": filters.assigne_a,
        "categorie": filters.categorie,
        "playbook_id": filters.playbook_id,
        "log_id": filters.log_id,
    }
    incidents, total = repository.fetch_incidents_page(
        database_session, filter_values, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse[IncidentListItemRead](
        items=build_incident_list_items(database_session, incidents),
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def fetch_incident_ids_by_log_ids(database_session: Session, log_ids: Iterable[UUID]) -> dict[UUID, UUID]:
    """Retourne {log_id: incident_id} pour les logs qui ont déjà un incident (liste des alertes)."""
    return repository.fetch_incident_ids_by_log_ids(database_session, log_ids)


def change_incident_status(
    database_session: Session, incident_id: UUID, status_change: IncidentStatusChangeRequest
) -> IncidentDetailRead:
    """Change le statut et maintient `closed_at` et `traite_le` cohérents. Lève ResourceNotFoundError."""
    incident = fetch_existing_incident(database_session, incident_id, is_locked_for_update=True)
    previous_status = IncidentStatus(incident.statut)
    new_status = status_change.statut
    if previous_status != new_status:
        # Horloge de la base, comme `created_at` : garantit closed_at/traite_le >= created_at (contraintes CHECK).
        if new_status == IncidentStatus.CLOSED:
            incident.closed_at = func.now()
        elif previous_status == IncidentStatus.CLOSED:
            incident.closed_at = None
        if new_status in HANDLED_INCIDENT_STATUSES and previous_status not in HANDLED_INCIDENT_STATUSES:
            incident.traite_le = func.now()
        elif new_status not in HANDLED_INCIDENT_STATUSES:
            incident.traite_le = None
        incident.statut = new_status.value
        record_incident_audit_event(
            database_session,
            incident,
            AuditEventType.INCIDENT_UPDATED,
            f"statut {previous_status.value} → {new_status.value}.",
            {"champ": "statut", "avant": previous_status.value, "apres": new_status.value},
        )
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_current_criticality(
    database_session: Session, incident_id: UUID, criticality_change: IncidentCriticalityChangeRequest
) -> IncidentDetailRead:
    """Réévalue la criticité actuelle (hausse ou baisse). La criticité source du log reste intacte.

    La date limite de traitement suit la nouvelle criticité (elle est calculée, pas stockée).
    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    _change_incident_field(database_session, incident, "criticite_actuelle", criticality_change.criticite_actuelle.value)
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_title(
    database_session: Session, incident_id: UUID, title_change: IncidentTitleChangeRequest
) -> IncidentDetailRead:
    """Renomme l'incident. Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé."""
    incident = fetch_modifiable_incident(database_session, incident_id)
    _change_incident_field(database_session, incident, "titre", title_change.titre)
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_category(
    database_session: Session, incident_id: UUID, category_change: IncidentCategoryChangeRequest
) -> IncidentDetailRead:
    """Change la catégorie. Le playbook déjà attribué est conservé (le changer est une action distincte).

    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    _change_incident_field(database_session, incident, "categorie", category_change.categorie)
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_false_positive_qualification(
    database_session: Session, incident_id: UUID, qualification: IncidentFalsePositiveQualificationRequest
) -> IncidentDetailRead:
    """Déclare l'incident faux positif (justification obligatoire) ou retire cette qualification.

    Ne change pas le statut : le lien entre faux positif et statut n'est pas encore décidé (cadrage, section 9).
    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    incident.faux_positif = qualification.faux_positif
    if qualification.justification is not None:
        incident.justification = qualification.justification
    if database_session.is_modified(incident):
        record_incident_audit_event(
            database_session,
            incident,
            AuditEventType.INCIDENT_UPDATED,
            "qualifié faux positif." if qualification.faux_positif else "qualification de faux positif retirée.",
            {"champ": "faux_positif", "apres": qualification.faux_positif},
        )
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_assignment(
    database_session: Session, incident_id: UUID, assignment: IncidentAssignmentRequest
) -> IncidentDetailRead:
    """Attribue l'incident (`assigne_a` en texte libre, provisoire) ou retire l'attribution (`None`).

    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    _change_incident_field(database_session, incident, "assigne_a", assignment.assigne_a)
    return commit_and_build_incident_detail(database_session, incident)


def change_incident_playbook(
    database_session: Session, incident_id: UUID, playbook_assignment: IncidentPlaybookAssignmentRequest
) -> IncidentDetailRead:
    """Attribue un playbook à l'incident, ou le retire (`None`).

    L'avancement déjà saisi sur un autre playbook est conservé en base mais ne compte plus (seules les étapes du
    playbook actuel comptent) : revenir au playbook précédent retrouve donc l'avancement.
    Lève ResourceNotFoundError (incident ou playbook absent), ou ResourceConflictError si l'incident est clôturé.
    """
    incident = fetch_modifiable_incident(database_session, incident_id)
    new_playbook_id = playbook_assignment.playbook_id
    if new_playbook_id is not None:
        playbooks_service.fetch_playbook_detail(database_session, new_playbook_id)
    _change_incident_field(database_session, incident, "playbook_id", new_playbook_id)
    return commit_and_build_incident_detail(database_session, incident)


def fetch_existing_incident(database_session: Session, incident_id: UUID, is_locked_for_update: bool = False) -> Incident:
    """Charge l'incident. Lève ResourceNotFoundError s'il n'existe pas (usage interne à la fonctionnalité)."""
    incident = repository.fetch_incident_by_id(database_session, incident_id, is_locked_for_update)
    if incident is None:
        raise ResourceNotFoundError(f"Incident {incident_id} introuvable.")
    return incident


def fetch_modifiable_incident(database_session: Session, incident_id: UUID) -> Incident:
    """Charge l'incident verrouillé et refuse la modification s'il est clôturé (règle provisoire)."""
    incident = fetch_existing_incident(database_session, incident_id, is_locked_for_update=True)
    if incident.statut == IncidentStatus.CLOSED:
        raise ResourceConflictError(f"L'incident {incident_id} est clôturé : rouvrez-le avant de le modifier.")
    return incident


def commit_and_build_incident_detail(database_session: Session, incident: Incident) -> IncidentDetailRead:
    """Valide la transaction et retourne le détail à jour (usage interne à la fonctionnalité)."""
    # Sans modification, SQLAlchemy n'émet aucun UPDATE : `updated_at` reste inchangé et le commit libère le verrou.
    has_pending_changes = database_session.is_modified(incident)
    database_session.commit()
    if has_pending_changes:
        database_session.refresh(incident)
    return build_incident_detail(database_session, incident)


def _change_incident_field(database_session: Session, incident: Incident, field_name: str, new_value) -> None:
    """Change un champ simple et trace le changement ; ne fait rien si la valeur est identique."""
    previous_value = getattr(incident, field_name)
    if previous_value == new_value:
        return
    setattr(incident, field_name, new_value)
    record_incident_audit_event(
        database_session,
        incident,
        AuditEventType.INCIDENT_UPDATED,
        f"{field_name} modifié.",
        {
            "champ": field_name,
            "avant": None if previous_value is None else str(previous_value),
            "apres": None if new_value is None else str(new_value),
        },
    )
