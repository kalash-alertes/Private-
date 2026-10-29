"""Accès base de données pour les tables `playbooks` et `etapes_playbook`. Aucune règle métier ici (voir `service.py`)."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.features.playbooks.models import Playbook, PlaybookStep


def add_playbook(database_session: Session, playbook: Playbook) -> None:
    """Ajoute le playbook (et ses étapes) à la session puis l'écrit (flush) : une violation d'unicité lève ici."""
    database_session.add(playbook)
    database_session.flush()


def fetch_playbook_by_id(
    database_session: Session, playbook_id: UUID, is_locked_for_update: bool = False
) -> Playbook | None:
    """Retourne le playbook avec ses étapes, ou None. `is_locked_for_update` : SELECT ... FOR UPDATE."""
    query = select(Playbook).where(Playbook.id == playbook_id).options(selectinload(Playbook.etapes))
    if is_locked_for_update:
        query = query.with_for_update()
    return database_session.scalars(query).one_or_none()


def fetch_playbook_id_by_name(database_session: Session, nom: str) -> UUID | None:
    return database_session.scalar(select(Playbook.id).where(Playbook.nom == nom))


def fetch_playbook_id_by_category(database_session: Session, categorie: str) -> UUID | None:
    return database_session.scalar(select(Playbook.id).where(Playbook.categorie == categorie))


def fetch_playbooks_with_step_counts(
    database_session: Session, categorie: str | None, limit: int, offset: int
) -> tuple[list[tuple[Playbook, int]], int]:
    """Retourne une page de (playbook, nombre d'étapes), triés par nom, et le total."""
    filter_conditions = [Playbook.categorie == categorie] if categorie is not None else []
    step_count_subquery = (
        select(PlaybookStep.playbook_id, func.count(PlaybookStep.id).label("nombre_etapes"))
        .group_by(PlaybookStep.playbook_id)
        .subquery()
    )
    total = database_session.scalar(select(func.count()).select_from(Playbook).where(*filter_conditions))
    rows = database_session.execute(
        select(Playbook, func.coalesce(step_count_subquery.c.nombre_etapes, 0))
        .outerjoin(step_count_subquery, step_count_subquery.c.playbook_id == Playbook.id)
        .where(*filter_conditions)
        .order_by(Playbook.nom, Playbook.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [(playbook, step_count) for playbook, step_count in rows], total or 0


def fetch_playbooks_with_steps_by_ids(database_session: Session, playbook_ids: Iterable[UUID]) -> list[Playbook]:
    """Retourne les playbooks demandés avec leurs étapes (en une requête par table)."""
    unique_playbook_ids = set(playbook_ids)
    if not unique_playbook_ids:
        return []
    return list(
        database_session.scalars(
            select(Playbook).where(Playbook.id.in_(unique_playbook_ids)).options(selectinload(Playbook.etapes))
        ).all()
    )


def delete_playbook(database_session: Session, playbook: Playbook) -> None:
    database_session.delete(playbook)
    database_session.flush()
