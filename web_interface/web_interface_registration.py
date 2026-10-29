"""Branchement de l'interface web sur l'application FastAPI : pages, fichiers statiques, pages d'erreur HTML.

Appelé par `backend/main.py`. Les erreurs des pages (adresses hors /api) sont affichées en HTML ; celles de l'API
gardent leur format JSON (`{"detail", "error_code"}`).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler

from backend.core.domain_errors import DomainError
from backend.core.http_error_handlers import (
    convert_domain_error_to_json_response,
    find_http_status_code_for_domain_error,
)
from web_interface.pages.alerts_page import alerts_page_router
from web_interface.pages.dashboard_page import dashboard_page_router
from web_interface.pages.incident_detail_page import incident_detail_page_router
from web_interface.pages.incidents_page import incidents_page_router
from web_interface.pages.journals_page import journals_page_router
from web_interface.pages.playbooks_pages import playbooks_pages_router
from web_interface.pages.settings_audit_journal_page import settings_audit_journal_page_router
from web_interface.pages.settings_incident_response_page import settings_incident_response_page_router
from web_interface.pages.settings_placeholder_pages import settings_placeholder_pages_router
from web_interface.template_rendering import page_templates

STATIC_FILES_DIRECTORY = Path(__file__).resolve().parent / "static"

PAGE_ROUTERS = [
    dashboard_page_router,
    incidents_page_router,
    incident_detail_page_router,
    alerts_page_router,
    journals_page_router,
    settings_incident_response_page_router,
    playbooks_pages_router,
    settings_audit_journal_page_router,
    settings_placeholder_pages_router,
]

ERROR_TITLES_BY_STATUS_CODE = {404: "Page introuvable", 409: "Action impossible", 422: "Demande invalide"}


def register_web_interface(application: FastAPI, api_path_prefix: str) -> None:
    """Ajoute les pages et les fichiers statiques ; installe les gestionnaires d'erreurs HTML/JSON selon l'adresse."""
    application.mount("/static", StaticFiles(directory=str(STATIC_FILES_DIRECTORY)), name="static")
    for page_router in PAGE_ROUTERS:
        application.include_router(page_router, include_in_schema=False)

    def is_api_request(request: Request) -> bool:
        return request.url.path.startswith(f"{api_path_prefix}/") or request.url.path.startswith("/static/")

    async def handle_domain_error(request: Request, domain_error: DomainError):
        if is_api_request(request):
            return await convert_domain_error_to_json_response(request, domain_error)
        return _render_error_page(request, find_http_status_code_for_domain_error(domain_error), domain_error.message)

    async def handle_request_validation_error(request: Request, validation_error: RequestValidationError):
        if is_api_request(request):
            return await request_validation_exception_handler(request, validation_error)
        return _render_error_page(request, 422, "Un paramètre de l'adresse ou du formulaire est invalide.")

    async def handle_http_error(request: Request, http_error: StarletteHTTPException):
        if is_api_request(request) or http_error.status_code not in ERROR_TITLES_BY_STATUS_CODE:
            return await http_exception_handler(request, http_error)
        return _render_error_page(request, http_error.status_code, "Cette page n'existe pas.")

    application.add_exception_handler(DomainError, handle_domain_error)
    application.add_exception_handler(RequestValidationError, handle_request_validation_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_error)


def _render_error_page(request: Request, status_code: int, error_message: str):
    return page_templates.TemplateResponse(
        request=request,
        name="pages/error.html",
        context={"error_title": ERROR_TITLES_BY_STATUS_CODE.get(status_code, "Erreur"), "error_message": error_message},
        status_code=status_code,
    )
