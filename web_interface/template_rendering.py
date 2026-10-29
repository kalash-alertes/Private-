"""Configuration du moteur de gabarits Jinja2 et fonction de rendu commune à toutes les pages.

Les filtres de `display_formatting.py` et la fonction `icon(...)` sont disponibles dans tous les gabarits.
L'échappement HTML automatique est actif : toute donnée (titre d'incident, log...) est affichée comme du texte.
"""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web_interface import display_formatting
from web_interface.icons import render_icon

TEMPLATES_DIRECTORY = Path(__file__).resolve().parent / "templates"

page_templates = Jinja2Templates(directory=str(TEMPLATES_DIRECTORY))
page_templates.env.globals["icon"] = render_icon
page_templates.env.globals["criticality_levels"] = display_formatting.CRITICALITY_LEVELS_FROM_MOST_SEVERE
page_templates.env.filters.update(
    {
        "criticality_label": display_formatting.format_criticality_label,
        "criticality_css": display_formatting.format_criticality_css_suffix,
        "incident_status_label": display_formatting.format_incident_status_label,
        "incident_status_css": display_formatting.format_incident_status_css_suffix,
        "import_run_status_label": display_formatting.format_import_run_status_label,
        "import_run_status_css": display_formatting.format_import_run_status_css_suffix,
        "audit_event_type_label": display_formatting.format_audit_event_type_label,
        "audit_event_type_css": display_formatting.format_audit_event_type_css_suffix,
        "display_datetime": display_formatting.format_datetime_for_display,
        "duration": display_formatting.format_duration_in_minutes,
        "initials": display_formatting.build_person_initials,
        "number": display_formatting.format_number,
    }
)


def render_page(
    request: Request, template_name: str, page_context: dict[str, Any], status_code: int = 200
) -> HTMLResponse:
    """Rend un gabarit de `templates/pages/` avec son contexte (qui inclut le contexte commun de mise en page)."""
    return page_templates.TemplateResponse(
        request=request, name=f"pages/{template_name}", context=page_context, status_code=status_code
    )
