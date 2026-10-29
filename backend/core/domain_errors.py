"""Erreurs métier communes levées par les services des fonctionnalités.

Les services ne connaissent pas HTTP : ils lèvent ces erreurs, et `backend/core/http_error_handlers.py`
les traduit en réponses HTTP (404, 409, 422). Les messages sont destinés aux utilisateurs de l'API :
ils ne doivent contenir ni secret ni donnée brute de log.
"""


class DomainError(Exception):
    """Classe parente des erreurs métier. `error_code` est un identifiant stable, exploitable par le frontend."""

    error_code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(DomainError):
    """La ressource demandée (exécution, log, incident) n'existe pas."""

    error_code = "resource_not_found"


class ResourceConflictError(DomainError):
    """L'opération contredit l'état actuel des données (doublon, exécution déjà terminée, incident clôturé...)."""

    error_code = "resource_conflict"


class BusinessRuleViolationError(DomainError):
    """Les données sont bien formées mais enfreignent une règle métier."""

    error_code = "business_rule_violation"
