"""Règles métier des playbooks (Paramètres > Réponse aux incidents > Playbooks).

Règles appliquées :
- un playbook = un nom unique + une source obligatoire + au moins une étape, dans l'ordre de la liste fournie ;
- une source est OBLIGATOIRE : l'application ne présente jamais une procédure sans référence vérifiable (AGENTS.md) ;
- une catégorie d'incident a au plus un playbook (il est proposé automatiquement aux nouveaux incidents de cette catégorie) ;
- modifier un playbook remplace la liste de ses étapes. Une étape envoyée avec son `id` est conservée, ce qui préserve
  son suivi (« étape réalisée ») dans les incidents ; une étape absente de la liste est supprimée avec son suivi ;
- supprimer un playbook le détache des incidents qui l'utilisaient (ils n'ont alors plus de plan) ;
- chaque création, modification et suppression est tracée dans le journal d'audit.

Fonctions publiques utilisables par les autres fonctionnalités :
- `find_playbook_id_for_category`, `fetch_playbook_detail`, `fetch_playbook_details_by_ids` : utilisées par `incidents`.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.domain_errors import BusinessRuleViolationError, ResourceConflictError, ResourceNotFoundError
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import NewAuditEventData
from backend.features.playbooks import repository
from backend.features.playbooks.models import Playbook, PlaybookStep
from backend.features.playbooks.schemas import (
    PlaybookDetailRead,
    PlaybookListFilters,
    PlaybookSummaryRead,
    PlaybookWriteRequest,
)

# Décalage provisoire des positions pendant un réordonnancement : évite que deux étapes partagent un instant la même
# position, ce que la contrainte UNIQUE(playbook_id, ordre) refuserait.
TEMPORARY_STEP_ORDER_OFFSET = 1_000_000


def create_playbook(
    database_session: Session, playbook_request: PlaybookWriteRequest, acteur: str | None = None
) -> PlaybookDetailRead:
    """Crée un playbook et ses étapes. Lève ResourceConflictError si le nom ou la catégorie est déjà utilisé."""
    _ensure_name_and_category_are_available(database_session, playbook_request, current_playbook_id=None)
    playbook = Playbook(
        nom=playbook_request.nom,
        description=playbook_request.description,
        categorie=playbook_request.categorie,
        source=playbook_request.source,
        etapes=[
            PlaybookStep(ordre=position, titre=step_request.titre, description=step_request.description)
            for position, step_request in enumerate(playbook_request.etapes, start=1)
        ],
    )
    _write_or_raise_conflict(database_session, lambda: repository.add_playbook(database_session, playbook))
    _record_playbook_event(
        database_session, AuditEventType.PLAYBOOK_CREATED, playbook, f"Playbook « {playbook.nom} » créé.", acteur
    )
    return _commit_and_build_playbook_detail(database_session, playbook)


def update_playbook(
    database_session: Session, playbook_id: UUID, playbook_request: PlaybookWriteRequest, acteur: str | None = None
) -> PlaybookDetailRead:
    """Remplace le playbook (champs + liste d'étapes).

    Lève ResourceNotFoundError (playbook absent), BusinessRuleViolationError (id d'étape n'appartenant pas à ce
    playbook), ResourceConflictError (nom ou catégorie déjà utilisé par un autre playbook).
    """
    playbook = _fetch_existing_playbook(database_session, playbook_id, is_locked_for_update=True)
    existing_steps_by_id = {step.id: step for step in playbook.etapes}
    unknown_step_ids = {step.id for step in playbook_request.etapes if step.id is not None} - existing_steps_by_id.keys()
    if unknown_step_ids:
        raise BusinessRuleViolationError(
            f"Étape(s) inconnue(s) pour ce playbook : {', '.join(sorted(str(step_id) for step_id in unknown_step_ids))}."
        )
    _ensure_name_and_category_are_available(database_session, playbook_request, current_playbook_id=playbook_id)

    def replace_playbook_content() -> None:
        playbook.nom = playbook_request.nom
        playbook.description = playbook_request.description
        playbook.categorie = playbook_request.categorie
        playbook.source = playbook_request.source
        # 1) Supprime les étapes retirées et écarte les positions des étapes conservées.
        kept_step_ids = {step.id for step in playbook_request.etapes if step.id is not None}
        for existing_step in list(playbook.etapes):
            if existing_step.id in kept_step_ids:
                existing_step.ordre += TEMPORARY_STEP_ORDER_OFFSET
            else:
                playbook.etapes.remove(existing_step)
        database_session.flush()
        # 2) Applique l'ordre final de la liste reçue (positions 1..n, sans trou).
        ordered_steps = []
        for position, step_request in enumerate(playbook_request.etapes, start=1):
            step = existing_steps_by_id[step_request.id] if step_request.id is not None else PlaybookStep()
            step.ordre = position
            step.titre = step_request.titre
            step.description = step_request.description
            ordered_steps.append(step)
        playbook.etapes = ordered_steps
        database_session.flush()

    _write_or_raise_conflict(database_session, replace_playbook_content)
    _record_playbook_event(
        database_session, AuditEventType.PLAYBOOK_UPDATED, playbook, f"Playbook « {playbook.nom} » modifié.", acteur
    )
    return _commit_and_build_playbook_detail(database_session, playbook)


def delete_playbook(database_session: Session, playbook_id: UUID, acteur: str | None = None) -> None:
    """Supprime le playbook et ses étapes ; les incidents liés n'ont plus de playbook. Lève ResourceNotFoundError."""
    playbook = _fetch_existing_playbook(database_session, playbook_id, is_locked_for_update=True)
    _record_playbook_event(
        database_session, AuditEventType.PLAYBOOK_DELETED, playbook, f"Playbook « {playbook.nom} » supprimé.", acteur
    )
    repository.delete_playbook(database_session, playbook)
    database_session.commit()


def list_playbooks(
    database_session: Session, filters: PlaybookListFilters, pagination: PaginationParameters
) -> PaginatedResponse[PlaybookSummaryRead]:
    """Retourne une page de playbooks, triés par nom, avec leur nombre d'étapes."""
    playbooks_with_step_counts, total = repository.fetch_playbooks_with_step_counts(
        database_session, filters.categorie, limit=pagination.limit, offset=pagination.offset
    )
    return PaginatedResponse[PlaybookSummaryRead](
        items=[
            PlaybookSummaryRead(
                id=playbook.id,
                nom=playbook.nom,
                categorie=playbook.categorie,
                nombre_etapes=step_count,
                updated_at=playbook.updated_at,
            )
            for playbook, step_count in playbooks_with_step_counts
        ],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def fetch_playbook_detail(database_session: Session, playbook_id: UUID) -> PlaybookDetailRead:
    """Retourne le playbook avec ses étapes ordonnées. Lève ResourceNotFoundError s'il n'existe pas."""
    return PlaybookDetailRead.model_validate(_fetch_existing_playbook(database_session, playbook_id))


def fetch_playbook_details_by_ids(
    database_session: Session, playbook_ids: Iterable[UUID]
) -> dict[UUID, PlaybookDetailRead]:
    """Retourne les playbooks demandés, indexés par id (les id inexistants sont absents du résultat)."""
    return {
        playbook.id: PlaybookDetailRead.model_validate(playbook)
        for playbook in repository.fetch_playbooks_with_steps_by_ids(database_session, playbook_ids)
    }


def find_playbook_id_for_category(database_session: Session, categorie: str) -> UUID | None:
    """Retourne l'id du playbook de cette catégorie d'incident, ou None s'il n'y en a pas."""
    return repository.fetch_playbook_id_by_category(database_session, categorie)


def _ensure_name_and_category_are_available(
    database_session: Session, playbook_request: PlaybookWriteRequest, current_playbook_id: UUID | None
) -> None:
    # Vérification préalable pour un message clair ; la contrainte UNIQUE reste l'arbitre en cas de concurrence.
    playbook_id_with_same_name = repository.fetch_playbook_id_by_name(database_session, playbook_request.nom)
    if playbook_id_with_same_name not in (None, current_playbook_id):
        raise ResourceConflictError(f"Un playbook nommé « {playbook_request.nom} » existe déjà.")
    if playbook_request.categorie is not None:
        playbook_id_with_same_category = repository.fetch_playbook_id_by_category(
            database_session, playbook_request.categorie
        )
        if playbook_id_with_same_category not in (None, current_playbook_id):
            raise ResourceConflictError(f"La catégorie « {playbook_request.categorie} » a déjà un playbook.")


def _write_or_raise_conflict(database_session: Session, write_operation) -> None:
    """Exécute l'écriture ; une violation d'unicité concurrente devient une ResourceConflictError (409)."""
    try:
        write_operation()
    except IntegrityError as integrity_error:
        database_session.rollback()
        raise ResourceConflictError("Nom ou catégorie de playbook déjà utilisé.") from integrity_error


def _fetch_existing_playbook(
    database_session: Session, playbook_id: UUID, is_locked_for_update: bool = False
) -> Playbook:
    playbook = repository.fetch_playbook_by_id(database_session, playbook_id, is_locked_for_update)
    if playbook is None:
        raise ResourceNotFoundError(f"Playbook {playbook_id} introuvable.")
    return playbook


def _record_playbook_event(
    database_session: Session,
    event_type: AuditEventType,
    playbook: Playbook,
    description: str,
    acteur: str | None,
) -> None:
    audit_journal_service.record_audit_event(
        database_session,
        NewAuditEventData(
            type_evenement=event_type,
            description=description,
            acteur=acteur,
            type_ressource="playbook",
            identifiant_ressource=str(playbook.id),
        ),
    )


def _commit_and_build_playbook_detail(database_session: Session, playbook: Playbook) -> PlaybookDetailRead:
    database_session.commit()
    database_session.refresh(playbook)
    return PlaybookDetailRead.model_validate(playbook)
