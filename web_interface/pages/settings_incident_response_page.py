"""Paramètres > Réponse aux incidents (`/parametres/reponse-incidents`) : délais de traitement par sévérité et
escalade automatique. Les playbooks, autre partie de cette section, sont dans `playbooks_pages.py`.

Le délai est saisi avec une unité (minutes, heures, jours) puis converti en minutes, unité stockée en base.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.core.criticality import CriticalityLevel
from backend.core.database import get_database_session
from backend.core.domain_errors import DomainError
from backend.features.incident_response_settings import service as incident_response_settings_service
from backend.features.incident_response_settings.schemas import ResponseDeadlineRuleUpdateRequest
from backend.features.incidents import automatic_escalation
from web_interface.application_layout import build_application_layout_context
from web_interface.form_values import convert_blank_to_none, describe_action_error
from web_interface.template_rendering import render_page

settings_incident_response_page_router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_database_session)]

MINUTES_PER_DELAY_UNIT = {"minutes": 1, "heures": 60, "jours": 24 * 60}


@settings_incident_response_page_router.get("/parametres", response_class=RedirectResponse)
def redirect_to_default_settings_section() -> RedirectResponse:
    return RedirectResponse("/parametres/reponse-incidents", status_code=303)


@settings_incident_response_page_router.get("/parametres/reponse-incidents", response_class=HTMLResponse)
def show_incident_response_settings_page(
    request: Request, database_session: DatabaseSession, notice: str | None = None, escalades: int | None = None
) -> HTMLResponse:
    """Tableau des délais par sévérité, avec l'escalade automatique de chacune."""
    return render_incident_response_settings_page(request, database_session, notice, escalated_incident_count=escalades)


@settings_incident_response_page_router.post("/parametres/reponse-incidents/delais/{criticite}")
def update_response_deadline_rule_from_form(
    request: Request,
    criticite: CriticalityLevel,
    database_session: DatabaseSession,
    delai_valeur: Annotated[int, Form(ge=1)],
    delai_unite: Annotated[str, Form()],
    escalader_vers: Annotated[str, Form()] = "",
    escalade_automatique_activee: Annotated[str | None, Form()] = None,
):
    """Enregistre la règle d'une sévérité. Case « escalade » non cochée = champ absent du formulaire = désactivée."""
    try:
        if delai_unite not in MINUTES_PER_DELAY_UNIT:
            raise DomainError("Unité de délai inconnue.")
        incident_response_settings_service.update_response_deadline_rule(
            database_session,
            criticite,
            ResponseDeadlineRuleUpdateRequest(
                delai_traitement_minutes=delai_valeur * MINUTES_PER_DELAY_UNIT[delai_unite],
                escalade_automatique_activee=escalade_automatique_activee is not None,
                escalader_vers=convert_blank_to_none(escalader_vers),
            ),
        )
    except (DomainError, ValidationError) as action_error:
        database_session.rollback()
        return render_incident_response_settings_page(
            request, database_session, error_message=describe_action_error(action_error), status_code=422
        )
    return RedirectResponse("/parametres/reponse-incidents?notice=delai_modifie", status_code=303)


@settings_incident_response_page_router.post("/parametres/reponse-incidents/escalade")
def run_automatic_escalation_from_form(database_session: DatabaseSession) -> RedirectResponse:
    """Lance l'escalade maintenant (sans attendre la boucle périodique) et affiche le nombre d'incidents escaladés."""
    escalation_result = automatic_escalation.escalate_overdue_incidents(database_session)
    return RedirectResponse(
        f"/parametres/reponse-incidents?notice=escalade_executee&escalades={escalation_result.nombre_incidents_escalades}",
        status_code=303,
    )


def render_incident_response_settings_page(
    request: Request,
    database_session: Session,
    notice_key: str | None = None,
    error_message: str | None = None,
    status_code: int = 200,
    escalated_incident_count: int | None = None,
) -> HTMLResponse:
    rules = incident_response_settings_service.list_response_deadline_rules(database_session)
    return render_page(
        request,
        "settings_incident_response.html",
        {
            **build_application_layout_context(
                database_session,
                "parametres",
                "Paramètres",
                "Réponse aux incidents : délais de traitement, escalade automatique et playbooks.",
                notice_key=notice_key,
                error_message=error_message,
            ),
            "active_settings_section": "reponse_incidents",
            "active_incident_response_tab": "delais",
            "rule_rows": [
                {"rule": rule, **_split_minutes_into_display_unit(rule.delai_traitement_minutes)} for rule in rules
            ],
            "escalated_incident_count": escalated_incident_count,
        },
        status_code=status_code,
    )


def _split_minutes_into_display_unit(delay_minutes: int) -> dict[str, int | str]:
    """Choisit la plus grande unité qui exprime le délai sans reste (1440 → 1 jour, 90 → 90 minutes)."""
    for unit_name in ("jours", "heures"):
        if delay_minutes % MINUTES_PER_DELAY_UNIT[unit_name] == 0:
            return {"delay_value": delay_minutes // MINUTES_PER_DELAY_UNIT[unit_name], "delay_unit": unit_name}
    return {"delay_value": delay_minutes, "delay_unit": "minutes"}
