"""Règles métier du cycle de vie d'un incident.

Règles appliquées (les règles PROVISOIRES sont à confirmer, cf. docs/technical/incidents.md) :
- un incident naît d'un log existant ; un log ne donne au plus qu'un incident (V1) ;
- `criticite_actuelle` est initialisée avec la criticité source du log, qui n'est jamais modifiée ici ;
- PROVISOIRE : toutes les transitions de statut sont autorisées (aucun graphe de transitions n'est encore défini) ;
- passer à `cloture` fixe `closed_at` ; quitter `cloture` (réouverture) remet `closed_at` à NULL.
  Sans table d'historique, la date de la clôture précédente est alors perdue ;
- PROVISOIRE : un incident clôturé est en lecture seule (criticité, faux positif, attribution) : il faut le rouvrir
  pour le modifier. Objectif : que le contenu d'un incident clôturé (base du futur rapport) ne change pas en silence ;
- une demande qui ne change rien (même statut, même criticité, même responsable) ne modifie pas `updated_at`.
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.domain_errors import ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.incidents import repository
from backend.features.incidents.models import Incident, IncidentStatus
from backend.features.incidents.schemas import (
    IncidentAssignmentRequest,
    IncidentCriticalityChangeRequest,
    IncidentDetailRead,
    IncidentFalsePositiveQualificationRequest,
    IncidentListFilters,
    IncidentRead,
    IncidentStatusChangeRequest,
)
from backend.features.source_logs import service as source_logs_service


def create_incident_from_source_log(database_session: Session, log_id: UUID) -> IncidentDetailRead:
    """Crée un incident `nouveau` à partir d'un log, avec la criticité source comme criticité actuelle.

    Lève ResourceNotFoundError si le log n'existe pas, ResourceConflictError si le log a déjà un incident
    (y compris lorsque deux créations simultanées visent le même log).
    """
    source_log = source_logs_service.fetch_source_log_metadata(database_session, log_id)
    incident = repository.insert_incident_unless_log_already_has_one(
        database_session, log_id=log_id, criticite_actuelle=source_log.criticite_source.value
    )
    if incident is None:
        existing_incident = repository.fetch_incident_by_log_id(database_session, log_id)
        raise ResourceConflictError(
            f"Le log {log_id} a déjà un incident ({existing_incident.id if existing_incident else 'inconnu'})."
        )
    database_session.commit()
    database_session.refresh(incident)
    return _build_incident_detail(database_session, incident)


def fetch_incident_detail(database_session: Session, incident_id: UUID) -> IncidentDetailRead:
    """Retourne le détail d'un incident. Lève ResourceNotFoundError s'il n'existe pas."""
    return _build_incident_detail(database_session, _fetch_existing_incident(database_session, incident_id))


def list_incidents(
    database_session: Session, filters: IncidentListFilters, pagination: PaginationParameters
) -> PaginatedResponse[IncidentRead]:
    """Retourne une page d'incidents, les plus récents d'abord."""
    filter_values = {
        "statut": filters.statut.value if filters.statut else None,
        "criticite_actuelle": filters.criticite_actuelle.value if filters.criticite_actuelle else None,
        "faux_positif": filters.faux_positif,
        "assigne_a": filters.assigne_a,
        "log_id": filters.log_id,
    }
    incidents, total = repository.fetch_incidents_page(
        database_session, filter_values, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse[IncidentRead](
        items=[IncidentRead.model_validate(incident) for incident in incidents],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def change_incident_status(
    database_session: Session, incident_id: UUID, status_change: IncidentStatusChangeRequest
) -> IncidentDetailRead:
    """Change le statut et maintient `closed_at` cohérent (clôture / réouverture). Lève ResourceNotFoundError."""
    incident = _fetch_existing_incident(database_session, incident_id, is_locked_for_update=True)
    new_status = status_change.statut
    if incident.statut != new_status:
        if new_status == IncidentStatus.CLOSED:
            # Horloge de la base, comme `created_at` : garantit closed_at >= created_at (contrainte CHECK).
            incident.closed_at = func.now()
        elif incident.statut == IncidentStatus.CLOSED:
            incident.closed_at = None
        incident.statut = new_status.value
    return _commit_and_build_incident_detail(database_session, incident)


def change_incident_current_criticality(
    database_session: Session, incident_id: UUID, criticality_change: IncidentCriticalityChangeRequest
) -> IncidentDetailRead:
    """Réévalue la criticité actuelle (hausse ou baisse). La criticité source du log reste intacte.

    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = _fetch_modifiable_incident(database_session, incident_id)
    if incident.criticite_actuelle != criticality_change.criticite_actuelle:
        incident.criticite_actuelle = criticality_change.criticite_actuelle.value
    return _commit_and_build_incident_detail(database_session, incident)


def change_incident_false_positive_qualification(
    database_session: Session, incident_id: UUID, qualification: IncidentFalsePositiveQualificationRequest
) -> IncidentDetailRead:
    """Déclare l'incident faux positif (justification obligatoire) ou retire cette qualification.

    Ne change pas le statut : le lien entre faux positif et statut n'est pas encore décidé (cadrage, section 9).
    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = _fetch_modifiable_incident(database_session, incident_id)
    incident.faux_positif = qualification.faux_positif
    if qualification.justification is not None:
        incident.justification = qualification.justification
    return _commit_and_build_incident_detail(database_session, incident)


def change_incident_assignment(
    database_session: Session, incident_id: UUID, assignment: IncidentAssignmentRequest
) -> IncidentDetailRead:
    """Attribue l'incident (`assigne_a` en texte libre, provisoire) ou retire l'attribution (`None`).

    Lève ResourceNotFoundError, ou ResourceConflictError si l'incident est clôturé.
    """
    incident = _fetch_modifiable_incident(database_session, incident_id)
    if incident.assigne_a != assignment.assigne_a:
        incident.assigne_a = assignment.assigne_a
    return _commit_and_build_incident_detail(database_session, incident)


def _fetch_existing_incident(
    database_session: Session, incident_id: UUID, is_locked_for_update: bool = False
) -> Incident:
    incident = repository.fetch_incident_by_id(database_session, incident_id, is_locked_for_update)
    if incident is None:
        raise ResourceNotFoundError(f"Incident {incident_id} introuvable.")
    return incident


def _fetch_modifiable_incident(database_session: Session, incident_id: UUID) -> Incident:
    """Charge l'incident verrouillé et refuse la modification s'il est clôturé (règle provisoire)."""
    incident = _fetch_existing_incident(database_session, incident_id, is_locked_for_update=True)
    if incident.statut == IncidentStatus.CLOSED:
        raise ResourceConflictError(f"L'incident {incident_id} est clôturé : rouvrez-le avant de le modifier.")
    return incident


def _commit_and_build_incident_detail(database_session: Session, incident: Incident) -> IncidentDetailRead:
    # Sans modification, SQLAlchemy n'émet aucun UPDATE : `updated_at` reste inchangé et le commit libère le verrou.
    has_pending_changes = database_session.is_modified(incident)
    database_session.commit()
    if has_pending_changes:
        database_session.refresh(incident)
    return _build_incident_detail(database_session, incident)


def _build_incident_detail(database_session: Session, incident: Incident) -> IncidentDetailRead:
    source_log = source_logs_service.fetch_source_log_metadata(database_session, incident.log_id)
    return IncidentDetailRead.model_validate(
        {**IncidentRead.model_validate(incident).model_dump(), "criticite_source": source_log.criticite_source}
    )
