"""Règles métier des playbooks (Paramètres > Réponse aux incidents > Playbooks).

Règles appliquées :
- un playbook = un nom unique + une source obligatoire + au moins une étape, dans l'ordre de la liste fournie ;
- une source est OBLIGATOIRE : l'application ne présente jamais une procédure sans référence vérifiable (AGENTS.md) ;
- une catégorie d'incident a au plus un playbook (il est proposé automatiquement aux nouveaux incidents de cette catégorie) ;
- modifier un playbook remplace la liste de ses étapes. Une étape envoyée avec son `id` est conservée, ce qui préserve
  son suivi (« étape réalisée ») dans les incidents ; une étape absente de la liste est supprimée avec son suivi ;
- supprimer un playbook le détache des incidents qui l'utilisaient (ils n'ont alors plus de plan) ;
- chaque création, modification et suppression est tracée dans le journal d'audit ;
- un playbook est d'abord un FICHIER JSON lisible (`playbook_files.py`, dossier `PLAYBOOK_FILES_DIRECTORY`) ; la base
  en est l'index. Créer, modifier, supprimer écrit le fichier ET la base : le fichier est écrit après les contrôles de
  la base (flush), avant la validation (commit) ; si la validation échoue, le fichier est remis dans son état
  précédent, et si l'écriture du fichier échoue, la base est annulée. Les deux restent donc alignés ;
- `synchronize_playbooks_with_files` (au démarrage, bouton « Synchroniser », script) enregistre en base les fichiers
  ajoutés ou modifiés à la main et écrit le fichier des playbooks qui n'en ont pas. Un fichier supprimé à la main ne
  supprime PAS le playbook (des incidents l'utilisent peut-être) : il est réécrit ; supprimer passe par l'interface.

Fonctions publiques utilisables par les autres fonctionnalités :
- `find_playbook_id_for_category`, `fetch_playbook_detail`, `fetch_playbook_details_by_ids` : utilisées par `incidents`.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.domain_errors import (
    BusinessRuleViolationError,
    DomainError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.core.pagination import PaginatedResponse, PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import NewAuditEventData
from backend.features.playbooks import playbook_files, repository
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
FILE_SYNCHRONIZATION_ACTOR = "synchronisation des fichiers de playbooks"

playbooks_logger = logging.getLogger(__name__)


def create_playbook(
    database_session: Session,
    playbook_request: PlaybookWriteRequest,
    acteur: str | None = None,
    playbook_id: UUID | None = None,
    current_file_path: Path | None = None,
) -> PlaybookDetailRead:
    """Crée un playbook, ses étapes et son fichier JSON. Lève ResourceConflictError si le nom ou la catégorie est déjà
    utilisé, BusinessRuleViolationError si le fichier ne peut pas être écrit.

    `playbook_id` / `current_file_path` : utilisés par la synchronisation (id déjà présent dans un fichier, fichier écrit
    à la main qui sera complété et renommé).
    """
    _ensure_name_and_category_are_available(database_session, playbook_request, current_playbook_id=None)
    playbook = Playbook(
        id=playbook_id or uuid4(),
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
    _commit_with_file_change(
        database_session, lambda: playbook_files.write_playbook_file(_build_file_of(playbook), current_file_path)
    )
    return _build_playbook_detail(database_session, playbook)


def update_playbook(
    database_session: Session,
    playbook_id: UUID,
    playbook_request: PlaybookWriteRequest,
    acteur: str | None = None,
    current_file_path: Path | None = None,
) -> PlaybookDetailRead:
    """Remplace le playbook (champs + liste d'étapes) et réécrit son fichier JSON.

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
    _commit_with_file_change(
        database_session, lambda: playbook_files.write_playbook_file(_build_file_of(playbook), current_file_path)
    )
    return _build_playbook_detail(database_session, playbook)


def delete_playbook(database_session: Session, playbook_id: UUID, acteur: str | None = None) -> None:
    """Supprime le playbook, ses étapes et son fichier JSON ; les incidents liés n'ont plus de playbook.
    Lève ResourceNotFoundError."""
    playbook = _fetch_existing_playbook(database_session, playbook_id, is_locked_for_update=True)
    _record_playbook_event(
        database_session, AuditEventType.PLAYBOOK_DELETED, playbook, f"Playbook « {playbook.nom} » supprimé.", acteur
    )
    repository.delete_playbook(database_session, playbook)
    _commit_with_file_change(database_session, lambda: playbook_files.delete_playbook_file(playbook_id))


@dataclass
class PlaybookFileSynchronizationReport:
    """Bilan d'une synchronisation fichiers → base (noms des playbooks, motifs des fichiers refusés)."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    # Playbooks présents en base sans fichier : leur fichier a été écrit.
    files_written: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def synchronize_playbooks_with_files(
    database_session: Session, acteur: str = FILE_SYNCHRONIZATION_ACTOR
) -> PlaybookFileSynchronizationReport:
    """Aligne la base sur les fichiers JSON du dossier des playbooks. Ne lève pas : chaque fichier refusé est noté.

    - fichier dont l'`id` (ou, sans `id`, le nom) est inconnu en base : playbook créé, fichier complété (ids) ;
    - fichier différent de la base : playbook mis à jour (étapes gardées par leur `id`, suivi des incidents préservé) ;
    - playbook en base sans fichier : son fichier est écrit.
    """
    report = PlaybookFileSynchronizationReport()
    synchronized_playbook_ids: set[UUID] = set()
    for file_reading in playbook_files.read_all_playbook_files():
        if file_reading.content is None:
            report.errors.append(file_reading.error)
            continue
        try:
            playbook_id = _synchronize_one_playbook_file(database_session, file_reading, acteur, report)
        except (DomainError, ValidationError) as synchronization_error:
            database_session.rollback()
            report.errors.append(f"{file_reading.path.name} : {synchronization_error}")
            continue
        if playbook_id in synchronized_playbook_ids:
            report.errors.append(f"{file_reading.path.name} : même playbook (id {playbook_id}) qu'un autre fichier.")
        synchronized_playbook_ids.add(playbook_id)

    for playbook in repository.fetch_all_playbooks_with_steps(database_session):
        if playbook.id not in synchronized_playbook_ids and playbook_files.find_playbook_file_path(playbook.id) is None:
            playbook_files.write_playbook_file(_build_file_of(playbook))
            report.files_written.append(playbook.nom)
    database_session.rollback()  # aucune écriture en attente : termine la transaction de lecture
    for error_message in report.errors:
        playbooks_logger.warning("Fichier de playbook ignoré : %s", error_message)
    return report


def _synchronize_one_playbook_file(
    database_session: Session,
    file_reading: playbook_files.PlaybookFileReading,
    acteur: str,
    report: PlaybookFileSynchronizationReport,
) -> UUID:
    file_content = file_reading.content
    playbook_request = file_content.to_write_request()
    playbook_id = file_content.id or repository.fetch_playbook_id_by_name(database_session, playbook_request.nom)
    existing_playbook = repository.fetch_playbook_by_id(database_session, playbook_id) if playbook_id else None
    if existing_playbook is None:
        created_playbook = create_playbook(
            database_session, playbook_request, acteur, playbook_id=file_content.id, current_file_path=file_reading.path
        )
        report.created.append(created_playbook.nom)
        return created_playbook.id
    if _playbook_matches_request(existing_playbook, playbook_request):
        if file_content.id is None or any(step.id is None for step in file_content.etapes):
            # Même contenu, mais fichier écrit à la main sans ids : on les ajoute pour lier fichier et base.
            playbook_files.write_playbook_file(_build_file_of(existing_playbook), file_reading.path)
        report.unchanged.append(existing_playbook.nom)
        return existing_playbook.id
    updated_playbook = update_playbook(
        database_session, existing_playbook.id, playbook_request, acteur, current_file_path=file_reading.path
    )
    report.updated.append(updated_playbook.nom)
    return updated_playbook.id


def _playbook_matches_request(playbook: Playbook, playbook_request: PlaybookWriteRequest) -> bool:
    return (
        (playbook.nom, playbook.description, playbook.categorie, playbook.source)
        == (playbook_request.nom, playbook_request.description, playbook_request.categorie, playbook_request.source)
        and [(step.id, step.titre, step.description) for step in playbook.etapes]
        == [(step.id, step.titre, step.description) for step in playbook_request.etapes]
    )


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


def _build_file_of(playbook: Playbook) -> playbook_files.PlaybookFile:
    """Contenu du fichier JSON d'un playbook de la session (étapes dans l'ordre, avec leurs id)."""
    ordered_steps = sorted(playbook.etapes, key=lambda step: step.ordre)
    return playbook_files.build_playbook_file(
        playbook.id,
        PlaybookWriteRequest.model_construct(
            nom=playbook.nom,
            description=playbook.description,
            categorie=playbook.categorie,
            source=playbook.source,
            etapes=ordered_steps,
        ),
        [step.id for step in ordered_steps],
    )


def _commit_with_file_change(
    database_session: Session, change_files: Callable[[], list[playbook_files.PreviousFileState]]
) -> None:
    """Écrit le(s) fichier(s) puis valide la base ; annule l'un si l'autre échoue (fichiers et base restent alignés)."""
    database_session.flush()
    try:
        previous_file_states = change_files()
    except OSError as file_error:
        database_session.rollback()
        raise BusinessRuleViolationError(
            f"Le fichier du playbook n'a pas pu être écrit ({file_error.strerror or type(file_error).__name__}) : "
            "rien n'a été enregistré."
        ) from file_error
    try:
        database_session.commit()
    except Exception:
        playbook_files.restore_files(previous_file_states)
        raise


def _build_playbook_detail(database_session: Session, playbook: Playbook) -> PlaybookDetailRead:
    database_session.refresh(playbook)
    return PlaybookDetailRead.model_validate(playbook)
