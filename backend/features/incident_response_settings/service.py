"""Règles des paramètres de réponse aux incidents (Paramètres > Réponse aux incidents).

- Une règle par criticité : délai de traitement (en minutes) et escalade automatique (activée ou non, cible éventuelle).
- La date limite d'un incident = sa date de création + le délai de sa criticité ACTUELLE (calculée par `incidents`) :
  modifier un délai ici déplace donc les dates limites des incidents existants. Choix assumé : la règle en vigueur
  s'applique partout, et réévaluer la criticité d'un incident change sa date limite.

Fonction publique utilisable par les autres fonctionnalités :
- `fetch_response_deadline_rules_by_criticality` : utilisée par `incidents` (dates limites, escalade).
"""

from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.domain_errors import ResourceNotFoundError
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.models import AuditEventType
from backend.features.audit_journal.schemas import NewAuditEventData
from backend.features.incident_response_settings import repository
from backend.features.incident_response_settings.schemas import (
    ResponseDeadlineRuleRead,
    ResponseDeadlineRuleUpdateRequest,
)

# Ordre d'affichage : de la plus grave à la moins grave.
CRITICALITY_DISPLAY_ORDER = [
    CriticalityLevel.CRITICAL,
    CriticalityLevel.HIGH,
    CriticalityLevel.MEDIUM,
    CriticalityLevel.LOW,
    CriticalityLevel.INFORMATION,
]


def list_response_deadline_rules(database_session: Session) -> list[ResponseDeadlineRuleRead]:
    """Retourne les règles, de la criticité la plus grave à la moins grave."""
    rules_by_criticality = fetch_response_deadline_rules_by_criticality(database_session)
    return [rules_by_criticality[level] for level in CRITICALITY_DISPLAY_ORDER if level in rules_by_criticality]


def fetch_response_deadline_rules_by_criticality(
    database_session: Session,
) -> dict[CriticalityLevel, ResponseDeadlineRuleRead]:
    """Retourne les règles indexées par criticité. Une criticité sans règle n'a pas de date limite."""
    return {
        CriticalityLevel(rule.criticite): ResponseDeadlineRuleRead.model_validate(rule)
        for rule in repository.fetch_all_response_deadline_rules(database_session)
    }


def update_response_deadline_rule(
    database_session: Session,
    criticite: CriticalityLevel,
    rule_update: ResponseDeadlineRuleUpdateRequest,
    acteur: str | None = None,
) -> ResponseDeadlineRuleRead:
    """Remplace la règle d'une criticité et trace le changement dans le journal d'audit.

    Lève ResourceNotFoundError si la ligne de cette criticité n'existe pas (base non migrée).
    """
    rule = repository.fetch_response_deadline_rule_by_criticality(database_session, criticite.value)
    if rule is None:
        raise ResourceNotFoundError(f"Aucune règle de délai pour la criticité {criticite.value}.")
    previous_values = ResponseDeadlineRuleRead.model_validate(rule).model_dump(
        mode="json", include={"delai_traitement_minutes", "escalade_automatique_activee", "escalader_vers"}
    )
    for field_name, field_value in rule_update.model_dump().items():
        setattr(rule, field_name, field_value)

    if database_session.is_modified(rule):
        audit_journal_service.record_audit_event(
            database_session,
            NewAuditEventData(
                type_evenement=AuditEventType.SETTINGS_UPDATED,
                description=f"Délai de réponse modifié pour la criticité {criticite.value}.",
                acteur=acteur,
                type_ressource="delai_reponse_incident",
                identifiant_ressource=criticite.value,
                details={"avant": previous_values, "apres": rule_update.model_dump(mode="json")},
            ),
        )
        database_session.commit()
        database_session.refresh(rule)
    else:
        database_session.commit()
    return ResponseDeadlineRuleRead.model_validate(rule)
