"""Paramètres > Réponse aux incidents > Playbooks (`/parametres/playbooks`) : bibliothèque, création, modification,
suppression. Un playbook = un nom, une source obligatoire et une liste d'étapes ordonnées.

Formulaire sans JavaScript : « Ajouter une étape » et « Supprimer » sont des boutons d'envoi (`action=...`) qui
renvoient le formulaire au serveur ; celui-ci le réaffiche modifié, sans rien enregistrer. Seul « Enregistrer »
appelle le service. Chaque étape garde son `id` caché : la conserver préserve son suivi dans les incidents.
"""

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from backend.core.database import get_database_session
from backend.core.domain_errors import DomainError
from backend.core.pagination import MAXIMUM_PAGE_SIZE, PaginationParameters
from backend.features.playbooks import service as playbooks_service
from backend.features.playbooks.schemas import (
    PlaybookDetailRead,
    PlaybookListFilters,
    PlaybookStepWriteRequest,
    PlaybookWriteRequest,
)
from web_interface.application_layout import build_application_layout_context
from web_interface.form_values import convert_blank_to_none, describe_action_error
from web_interface.template_rendering import render_page

playbooks_pages_router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_database_session)]

ADD_STEP_ACTION = "ajouter_etape"
REMOVE_STEP_ACTION_PREFIX = "supprimer_etape_"
SAVE_ACTION = "enregistrer"


@dataclass
class PlaybookStepDraft:
    """Étape telle que saisie dans le formulaire (pas encore validée)."""

    step_id: str = ""
    titre: str = ""
    description: str = ""


@dataclass
class PlaybookDraft:
    """Playbook tel que saisi dans le formulaire (pas encore validé)."""

    nom: str = ""
    description: str = ""
    categorie: str = ""
    source: str = ""
    etapes: list[PlaybookStepDraft] = field(default_factory=lambda: [PlaybookStepDraft()])


@playbooks_pages_router.get("/parametres/playbooks", response_class=HTMLResponse)
def show_playbooks_page(
    request: Request,
    database_session: DatabaseSession,
    recherche: Annotated[str | None, Query(max_length=255)] = None,
    notice: str | None = None,
) -> HTMLResponse:
    """Bibliothèque des playbooks (cartes), avec recherche par nom, catégorie ou description."""
    all_playbooks = playbooks_service.fetch_playbook_details_by_ids(
        database_session,
        [
            playbook_summary.id
            for playbook_summary in playbooks_service.list_playbooks(
                database_session, PlaybookListFilters(), PaginationParameters(limit=MAXIMUM_PAGE_SIZE)
            ).items
        ],
    ).values()
    search_text = (recherche or "").strip().lower()
    visible_playbooks = sorted(
        (
            playbook
            for playbook in all_playbooks
            if search_text in f"{playbook.nom} {playbook.categorie or ''} {playbook.description or ''}".lower()
        ),
        key=lambda playbook: playbook.nom.lower(),
    )
    return render_page(
        request,
        "playbooks.html",
        {
            **_build_playbooks_layout_context(database_session, notice_key=notice),
            "playbooks": visible_playbooks,
            "search_text": recherche or "",
        },
    )


@playbooks_pages_router.get("/parametres/playbooks/nouveau", response_class=HTMLResponse)
def show_new_playbook_form(request: Request, database_session: DatabaseSession) -> HTMLResponse:
    return _render_playbook_form(request, database_session, PlaybookDraft(), playbook_id=None)


@playbooks_pages_router.post("/parametres/playbooks/nouveau")
async def submit_new_playbook_form(request: Request, database_session: DatabaseSession):
    return await _handle_playbook_form_submission(request, database_session, playbook_id=None)


@playbooks_pages_router.get("/parametres/playbooks/{playbook_id}/modifier", response_class=HTMLResponse)
def show_edit_playbook_form(request: Request, playbook_id: UUID, database_session: DatabaseSession) -> HTMLResponse:
    """Formulaire prérempli (404 si le playbook n'existe pas)."""
    playbook = playbooks_service.fetch_playbook_detail(database_session, playbook_id)
    return _render_playbook_form(request, database_session, _convert_playbook_to_draft(playbook), playbook_id)


@playbooks_pages_router.post("/parametres/playbooks/{playbook_id}/modifier")
async def submit_edit_playbook_form(request: Request, playbook_id: UUID, database_session: DatabaseSession):
    return await _handle_playbook_form_submission(request, database_session, playbook_id=playbook_id)


@playbooks_pages_router.post("/parametres/playbooks/{playbook_id}/supprimer")
def delete_playbook_from_form(playbook_id: UUID, database_session: DatabaseSession) -> RedirectResponse:
    """Supprime le playbook (confirmé dans une fenêtre du formulaire) ; les incidents liés n'ont plus de plan."""
    playbooks_service.delete_playbook(database_session, playbook_id)
    return RedirectResponse("/parametres/playbooks?notice=playbook_supprime", status_code=303)


async def _handle_playbook_form_submission(request: Request, database_session: Session, playbook_id: UUID | None):
    submitted_form = await request.form()
    draft = _read_playbook_draft_from_form(submitted_form)
    requested_action = str(submitted_form.get("action", SAVE_ACTION))

    if requested_action == ADD_STEP_ACTION:
        draft.etapes.append(PlaybookStepDraft())
        return _render_playbook_form(request, database_session, draft, playbook_id)
    if requested_action.startswith(REMOVE_STEP_ACTION_PREFIX):
        removed_step_position = requested_action.removeprefix(REMOVE_STEP_ACTION_PREFIX)
        # Valeur venant du navigateur : un index non numérique ou hors limites est simplement ignoré.
        removed_step_index = int(removed_step_position) if removed_step_position.isdigit() else -1
        if 0 <= removed_step_index < len(draft.etapes) and len(draft.etapes) > 1:
            del draft.etapes[removed_step_index]
        return _render_playbook_form(request, database_session, draft, playbook_id)

    try:
        playbook_request = PlaybookWriteRequest(
            nom=draft.nom,
            description=convert_blank_to_none(draft.description),
            categorie=convert_blank_to_none(draft.categorie),
            source=draft.source,
            etapes=[
                PlaybookStepWriteRequest(
                    id=convert_blank_to_none(step.step_id),
                    titre=step.titre,
                    description=convert_blank_to_none(step.description),
                )
                for step in draft.etapes
            ],
        )
        if playbook_id is None:
            playbooks_service.create_playbook(database_session, playbook_request)
            notice_key = "playbook_cree"
        else:
            playbooks_service.update_playbook(database_session, playbook_id, playbook_request)
            notice_key = "playbook_modifie"
    except (DomainError, ValidationError) as action_error:
        database_session.rollback()
        return _render_playbook_form(
            request, database_session, draft, playbook_id, error_message=describe_action_error(action_error), status_code=422
        )
    return RedirectResponse(f"/parametres/playbooks?notice={notice_key}", status_code=303)


def _read_playbook_draft_from_form(submitted_form: FormData) -> PlaybookDraft:
    """Les étapes arrivent en listes parallèles (`etape_id`, `etape_titre`, `etape_description`), dans l'ordre affiché."""
    step_ids = submitted_form.getlist("etape_id")
    step_titles = submitted_form.getlist("etape_titre")
    step_descriptions = submitted_form.getlist("etape_description")
    return PlaybookDraft(
        nom=str(submitted_form.get("nom", "")),
        description=str(submitted_form.get("description", "")),
        categorie=str(submitted_form.get("categorie", "")),
        source=str(submitted_form.get("source", "")),
        etapes=[
            PlaybookStepDraft(step_id=str(step_id), titre=str(step_title), description=str(step_description))
            for step_id, step_title, step_description in zip(step_ids, step_titles, step_descriptions, strict=False)
        ]
        or [PlaybookStepDraft()],
    )


def _convert_playbook_to_draft(playbook: PlaybookDetailRead) -> PlaybookDraft:
    return PlaybookDraft(
        nom=playbook.nom,
        description=playbook.description or "",
        categorie=playbook.categorie or "",
        source=playbook.source,
        etapes=[
            PlaybookStepDraft(step_id=str(step.id), titre=step.titre, description=step.description or "")
            for step in playbook.etapes
        ],
    )


def _render_playbook_form(
    request: Request,
    database_session: Session,
    draft: PlaybookDraft,
    playbook_id: UUID | None,
    error_message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return render_page(
        request,
        "playbook_form.html",
        {
            **_build_playbooks_layout_context(database_session, error_message=error_message),
            "draft": draft,
            "playbook_id": playbook_id,
            "form_action": (
                "/parametres/playbooks/nouveau" if playbook_id is None else f"/parametres/playbooks/{playbook_id}/modifier"
            ),
            "add_step_action": ADD_STEP_ACTION,
            "remove_step_action_prefix": REMOVE_STEP_ACTION_PREFIX,
        },
        status_code=status_code,
    )


def _build_playbooks_layout_context(
    database_session: Session, notice_key: str | None = None, error_message: str | None = None
) -> dict:
    return {
        **build_application_layout_context(
            database_session,
            "playbooks",
            "Playbooks",
            "Procédures de réponse aux incidents : un nom, une source vérifiable et des étapes à suivre.",
            notice_key=notice_key,
            error_message=error_message,
        ),
        "active_settings_section": "reponse_incidents",
        "active_incident_response_tab": "playbooks",
    }
