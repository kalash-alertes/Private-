"""Accès base de données pour les tables `incidents` et `etapes_realisees_incident`.

Aucune règle métier ici (voir `service.py`).
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.features.incidents.models import Incident, IncidentPlaybookStepCompletion

# Deux créations simultanées peuvent calculer le même numéro de référence : la contrainte UNIQUE en refuse une,
# qui retente avec le numéro suivant. Au-delà de ce nombre d'essais, l'erreur est relancée (situation anormale).
MAXIMUM_REFERENCE_NUMBER_ATTEMPTS = 5


def insert_incident_unless_log_already_has_one(
    database_session: Session, incident_values: dict[str, Any]
) -> Incident | None:
    """Insère un incident (avec le prochain numéro de référence) ; retourne None si ce log a déjà un incident.

    Sûr en cas de créations concurrentes : les contraintes UNIQUE sur `log_id` et `numero_reference` arbitrent.
    Chaque tentative se fait dans un point de sauvegarde (SAVEPOINT) : en cas de violation, seul ce point est annulé et
    la session reste utilisable. Conflit sur le log ⇒ None ; conflit sur le numéro ⇒ nouvel essai.
    """
    log_id = incident_values["log_id"]
    for attempt_number in range(1, MAXIMUM_REFERENCE_NUMBER_ATTEMPTS + 1):
        incident = Incident(**incident_values, numero_reference=_compute_next_reference_number(database_session))
        try:
            with database_session.begin_nested():
                database_session.add(incident)
                database_session.flush()
        except IntegrityError:
            if fetch_incident_by_log_id(database_session, log_id) is not None:
                return None
            if attempt_number == MAXIMUM_REFERENCE_NUMBER_ATTEMPTS:
                raise
            continue
        return incident
    return None  # Inatteignable : la dernière tentative retourne ou relance.


def _compute_next_reference_number(database_session: Session) -> int:
    return (database_session.scalar(select(func.max(Incident.numero_reference))) or 0) + 1


def fetch_incident_by_log_id(database_session: Session, log_id: UUID) -> Incident | None:
    """Retourne l'incident lié à ce log, ou None."""
    return database_session.scalars(select(Incident).where(Incident.log_id == log_id)).one_or_none()


def fetch_incident_by_id(
    database_session: Session, incident_id: UUID, is_locked_for_update: bool = False
) -> Incident | None:
    """Retourne l'incident ou None.

    `is_locked_for_update` (SELECT ... FOR UPDATE) sérialise les modifications concurrentes d'un même incident :
    la seconde attend la fin de la première et applique ses règles sur l'état à jour (sans effet sur SQLite).
    """
    query = select(Incident).where(Incident.id == incident_id)
    if is_locked_for_update:
        query = query.with_for_update()
    return database_session.scalars(query).one_or_none()


def fetch_incidents_page(
    database_session: Session, filter_values: dict[str, Any], limit: int, offset: int
) -> tuple[list[Incident], int]:
    """Retourne une page d'incidents (les plus récents d'abord) et le total correspondant aux filtres.

    `filter_values` : colonnes d'`Incident` (égalité exacte), valeurs None ignorées ; clés spéciales `statuts`
    (ensemble de statuts acceptés, pour les onglets « en cours » / « traités ») et `recherche` (texte cherché, sans
    tenir compte de la casse, dans le titre, la catégorie et le responsable).
    """
    special_filter_keys = {"statuts", "recherche"}
    filter_conditions = [
        getattr(Incident, column_name) == filter_value
        for column_name, filter_value in filter_values.items()
        if filter_value is not None and column_name not in special_filter_keys
    ]
    if filter_values.get("statuts") is not None:
        filter_conditions.append(Incident.statut.in_(filter_values["statuts"]))
    if filter_values.get("recherche"):
        # Les caractères spéciaux de LIKE (% et _) saisis par l'utilisateur sont échappés : recherche littérale.
        escaped_search_text = (
            filter_values["recherche"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        search_pattern = f"%{escaped_search_text}%"
        filter_conditions.append(
            or_(
                Incident.titre.ilike(search_pattern, escape="\\"),
                Incident.categorie.ilike(search_pattern, escape="\\"),
                Incident.assigne_a.ilike(search_pattern, escape="\\"),
            )
        )
    total = database_session.scalar(select(func.count()).select_from(Incident).where(*filter_conditions))
    incidents = database_session.scalars(
        select(Incident)
        .where(*filter_conditions)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(incidents), total or 0


def fetch_open_incidents_not_yet_escalated_for_update(
    database_session: Session, open_statuses: Iterable[str]
) -> list[Incident]:
    """Retourne les incidents ouverts jamais escaladés, verrouillés.

    SKIP LOCKED : un incident en cours de modification par quelqu'un d'autre est ignoré ce tour-ci (il sera revu au
    suivant) au lieu de bloquer l'escalade. Sur PostgreSQL, la condition `escalade_le IS NULL` est réévaluée après
    verrouillage : deux escalades simultanées ne traitent jamais deux fois le même incident.
    """
    return list(
        database_session.scalars(
            select(Incident)
            .where(Incident.statut.in_(list(open_statuses)), Incident.escalade_le.is_(None))
            .order_by(Incident.created_at, Incident.id)
            .with_for_update(skip_locked=True)
        ).all()
    )


def fetch_completed_step_ids_by_incident_id(
    database_session: Session, incident_ids: Iterable[UUID]
) -> dict[UUID, set[UUID]]:
    """Retourne, pour chaque incident demandé, l'ensemble des id d'étapes de playbook marquées réalisées."""
    unique_incident_ids = set(incident_ids)
    completed_step_ids_by_incident_id: dict[UUID, set[UUID]] = {incident_id: set() for incident_id in unique_incident_ids}
    if not unique_incident_ids:
        return completed_step_ids_by_incident_id
    rows = database_session.execute(
        select(IncidentPlaybookStepCompletion.incident_id, IncidentPlaybookStepCompletion.etape_playbook_id).where(
            IncidentPlaybookStepCompletion.incident_id.in_(unique_incident_ids)
        )
    ).all()
    for incident_id, step_id in rows:
        completed_step_ids_by_incident_id[incident_id].add(step_id)
    return completed_step_ids_by_incident_id


def fetch_step_completions_for_incident(
    database_session: Session, incident_id: UUID
) -> list[IncidentPlaybookStepCompletion]:
    return list(
        database_session.scalars(
            select(IncidentPlaybookStepCompletion).where(IncidentPlaybookStepCompletion.incident_id == incident_id)
        ).all()
    )


def insert_step_completion_unless_exists(
    database_session: Session, incident_id: UUID, step_id: UUID, realisee_par: str | None
) -> None:
    """Marque l'étape réalisée ; sans effet si elle l'est déjà (contrainte UNIQUE, dans un SAVEPOINT)."""
    try:
        with database_session.begin_nested():
            database_session.add(
                IncidentPlaybookStepCompletion(
                    incident_id=incident_id, etape_playbook_id=step_id, realisee_par=realisee_par
                )
            )
            database_session.flush()
    except IntegrityError:
        existing_completion = database_session.scalar(
            select(IncidentPlaybookStepCompletion.id).where(
                IncidentPlaybookStepCompletion.incident_id == incident_id,
                IncidentPlaybookStepCompletion.etape_playbook_id == step_id,
            )
        )
        if existing_completion is None:
            raise


def delete_step_completion(database_session: Session, incident_id: UUID, step_id: UUID) -> int:
    """Retire la marque « réalisée » ; retourne le nombre de lignes supprimées (0 ou 1)."""
    return database_session.execute(
        delete(IncidentPlaybookStepCompletion).where(
            IncidentPlaybookStepCompletion.incident_id == incident_id,
            IncidentPlaybookStepCompletion.etape_playbook_id == step_id,
        )
    ).rowcount


def fetch_incident_ids_by_log_ids(database_session: Session, log_ids: Iterable[UUID]) -> dict[UUID, UUID]:
    """Retourne {log_id: incident_id} pour les logs demandés qui ont un incident."""
    unique_log_ids = set(log_ids)
    if not unique_log_ids:
        return {}
    rows = database_session.execute(select(Incident.log_id, Incident.id).where(Incident.log_id.in_(unique_log_ids))).all()
    return {log_id: incident_id for log_id, incident_id in rows}


def count_all_incidents(database_session: Session) -> int:
    return database_session.scalar(select(func.count()).select_from(Incident)) or 0


def fetch_incidents_with_statuses(database_session: Session, statuses: Iterable[str]) -> list[Incident]:
    """Retourne tous les incidents ayant l'un de ces statuts (pour les statistiques du tableau de bord)."""
    return list(database_session.scalars(select(Incident).where(Incident.statut.in_(list(statuses)))).all())
