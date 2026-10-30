"""Traduction des erreurs métier (`domain_errors.py`) en réponses HTTP homogènes.

Format de réponse : `{"detail": "<message lisible>", "error_code": "<identifiant stable>"}`.
Les erreurs de validation des requêtes restent gérées par FastAPI (422, format standard).
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.core.domain_errors import (
    BusinessRuleViolationError,
    DomainError,
    ResourceConflictError,
    ResourceNotFoundError,
)

HTTP_STATUS_CODE_BY_DOMAIN_ERROR: dict[type[DomainError], int] = {
    ResourceNotFoundError: status.HTTP_404_NOT_FOUND,
    ResourceConflictError: status.HTTP_409_CONFLICT,
    # 422 en littéral : le nom de la constante a changé selon les versions de Starlette.
    BusinessRuleViolationError: 422,
}


def find_http_status_code_for_domain_error(domain_error: DomainError) -> int:
    """Code HTTP correspondant à l'erreur métier (400 pour une erreur métier sans code dédié)."""
    return HTTP_STATUS_CODE_BY_DOMAIN_ERROR.get(type(domain_error), status.HTTP_400_BAD_REQUEST)


async def convert_domain_error_to_json_response(_request: Request, domain_error: DomainError) -> JSONResponse:
    """Réponse JSON de l'API pour une erreur métier."""
    return JSONResponse(
        status_code=find_http_status_code_for_domain_error(domain_error),
        content={"detail": domain_error.message, "error_code": domain_error.error_code},
    )


def register_domain_error_handlers(application: FastAPI) -> None:
    """Branche sur l'application le gestionnaire des erreurs métier (réponses JSON)."""
    application.add_exception_handler(DomainError, convert_domain_error_to_json_response)
