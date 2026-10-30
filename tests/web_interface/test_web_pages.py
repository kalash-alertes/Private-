"""Tests de l'interface web : chaque page s'affiche, et les formulaires réalisent les actions métier.

Les pages sont vérifiées par leur code HTTP et la présence de textes clés (pas de comparaison de HTML complet).
Données synthétiques uniquement.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.core.pagination import PaginationParameters
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.schemas import AuditEventListFilters
from backend.features.incidents import service as incidents_service
from backend.features.incidents.schemas import IncidentListFilters
from backend.features.playbooks import service as playbooks_service
from tests.synthetic_data import build_synthetic_playbook_request, store_synthetic_source_log

def end_test_session_transaction(database_session) -> None:
    """Termine la transaction de lecture ouverte par la préparation du test.

    Avec SQLite, une transaction ouverte (même en lecture) empêche la page appelée ensuite, qui utilise une autre
    connexion, de valider ses écritures (« database is locked »).
    """
    database_session.rollback()


PAGE_URLS = [
    "/",
    "/incidents",
    "/incidents?vue=traites",
    "/alertes",
    "/journaux",
    "/parametres/reponse-incidents",
    "/parametres/playbooks",
    "/parametres/playbooks/nouveau",
    "/parametres/journal-audit",
    "/parametres/clients",
    "/parametres/utilisateurs",
]


@pytest.mark.parametrize("page_url", PAGE_URLS)
def test_every_page_renders_on_an_empty_database(web_client, page_url) -> None:
    response = web_client.get(page_url)

    assert response.status_code == 200
    assert "FAnalyzer IR" in response.text and "<svg" in response.text


def test_settings_root_redirects_to_incident_response(web_client) -> None:
    response = web_client.get("/parametres")
    assert response.status_code == 303 and response.headers["location"] == "/parametres/reponse-incidents"


def test_static_stylesheets_are_served(web_client) -> None:
    response = web_client.get("/static/css/components.css")
    assert response.status_code == 200 and "severity-pill" in response.text


def test_incident_is_created_from_an_alert_and_opens_on_its_playbook(web_client, database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    storage_result = store_synthetic_source_log(database_session)
    end_test_session_transaction(database_session)
    assert "Créer l'incident" in web_client.get("/alertes").text

    creation_response = web_client.post("/incidents", data={"log_id": str(storage_result.source_log_id)})

    assert creation_response.status_code == 303
    incident_page_url = creation_response.headers["location"]
    incident_page = web_client.get(incident_page_url)
    assert incident_page.status_code == 200
    assert "INC-000001" in incident_page.text
    assert playbook.nom in incident_page.text and "Étape synthétique 1" in incident_page.text
    assert "Incident créé." in incident_page.text
    list_page = web_client.get("/incidents").text
    assert "INC-000001" in list_page and "0/3" in list_page


def test_incident_creation_errors_are_shown_on_the_page(web_client) -> None:
    unknown_log_response = web_client.post("/incidents", data={"log_id": str(uuid4())})
    invalid_log_response = web_client.post("/incidents", data={"log_id": "pas-un-uuid"})

    assert unknown_log_response.status_code == 422 and "introuvable" in unknown_log_response.text
    assert invalid_log_response.status_code == 422 and "Données invalides" in invalid_log_response.text


def test_incident_actions_through_forms(web_client, database_session) -> None:
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    storage_result = store_synthetic_source_log(database_session)
    end_test_session_transaction(database_session)
    incident_url = web_client.post("/incidents", data={"log_id": str(storage_result.source_log_id)}).headers["location"]
    incident_url = incident_url.split("?")[0]
    incident_id = incident_url.rsplit("/", 1)[1]
    first_step_id = incidents_service.list_incidents(
        database_session, IncidentListFilters(), PaginationParameters()
    ).items[0].plan.playbook_id
    first_step_id = playbooks_service.fetch_playbook_detail(database_session, first_step_id).etapes[0].id
    end_test_session_transaction(database_session)

    form_actions = [
        ("statut", {"statut": "en_cours"}),
        ("criticite", {"criticite_actuelle": "moyenne"}),
        ("assignation", {"assigne_a": "analyste.synthetique"}),
        ("titre-categorie", {"titre": "Titre modifié", "categorie": "synthetique_intrusion"}),
        ("faux-positif", {"faux_positif": "oui", "justification": "Test autorisé"}),
        (f"playbook/etapes/{first_step_id}", {"realisee": "oui", "realisee_par": "analyste.synthetique"}),
    ]
    for action_path, form_data in form_actions:
        response = web_client.post(f"{incident_url}/{action_path}", data=form_data)
        assert response.status_code == 303, action_path

    incident_page = web_client.get(incident_url).text
    assert "Titre modifié" in incident_page and "analyste.synthetique" in incident_page
    assert "Faux positif" in incident_page and "Réalisée le" in incident_page
    history = audit_journal_service.list_audit_events(
        database_session, AuditEventListFilters(identifiant_ressource=incident_id), PaginationParameters()
    )
    assert history.total == 7  # création + statut, criticité, responsable, titre, faux positif, étape
    end_test_session_transaction(database_session)

    missing_justification = web_client.post(f"{incident_url}/faux-positif", data={"faux_positif": "oui"})
    assert missing_justification.status_code == 422 and "justification" in missing_justification.text
    web_client.post(f"{incident_url}/statut", data={"statut": "cloture"})
    closed_response = web_client.post(f"{incident_url}/assignation", data={"assigne_a": "autre"})
    assert closed_response.status_code == 422 and "rouvrez-le" in closed_response.text


def test_playbook_form_adds_removes_steps_then_saves(web_client, database_session) -> None:
    base_form = {"nom": "Playbook formulaire", "categorie": "", "source": "Source synthétique", "description": ""}

    with_added_step = web_client.post(
        "/parametres/playbooks/nouveau",
        data={**base_form, "etape_id": [""], "etape_titre": ["Première"], "etape_description": [""], "action": "ajouter_etape"},
    )
    assert with_added_step.status_code == 200 and with_added_step.text.count('name="etape_titre"') == 2

    after_removal = web_client.post(
        "/parametres/playbooks/nouveau",
        data={
            **base_form,
            "etape_id": ["", ""],
            "etape_titre": ["Première", "Seconde"],
            "etape_description": ["", ""],
            "action": "supprimer_etape_0",
        },
    )
    assert after_removal.text.count('name="etape_titre"') == 1 and 'value="Seconde"' in after_removal.text

    saved = web_client.post(
        "/parametres/playbooks/nouveau",
        data={**base_form, "etape_id": [""], "etape_titre": ["Seconde"], "etape_description": ["Faire X"], "action": "enregistrer"},
    )
    assert saved.status_code == 303
    assert "Playbook formulaire" in web_client.get("/parametres/playbooks").text

    missing_source = web_client.post(
        "/parametres/playbooks/nouveau",
        data={**base_form, "source": "", "etape_id": [""], "etape_titre": ["X"], "etape_description": [""]},
    )
    assert missing_source.status_code == 422 and "Données invalides" in missing_source.text


def test_playbook_can_be_edited_and_deleted_through_forms(web_client, database_session) -> None:
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request(step_count=1))
    end_test_session_transaction(database_session)
    edit_url = f"/parametres/playbooks/{playbook.id}/modifier"
    assert web_client.get(edit_url).status_code == 200

    response = web_client.post(
        edit_url,
        data={
            "nom": "Nom modifié",
            "categorie": "",
            "source": "Source synthétique",
            "description": "",
            "etape_id": [str(playbook.etapes[0].id)],
            "etape_titre": ["Étape renommée"],
            "etape_description": [""],
            "action": "enregistrer",
        },
    )
    assert response.status_code == 303
    assert playbooks_service.fetch_playbook_detail(database_session, playbook.id).etapes[0].id == playbook.etapes[0].id
    end_test_session_transaction(database_session)

    assert web_client.post(f"/parametres/playbooks/{playbook.id}/supprimer").status_code == 303
    assert web_client.get(edit_url).status_code == 404


def test_response_delay_and_escalation_forms(web_client) -> None:
    saved = web_client.post(
        "/parametres/reponse-incidents/delais/haute",
        data={"delai_valeur": "2", "delai_unite": "heures", "escalade_automatique_activee": "on", "escalader_vers": "n2"},
    )
    assert saved.status_code == 303
    settings_page = web_client.get("/parametres/reponse-incidents").text
    assert 'value="2"' in settings_page and 'value="n2"' in settings_page

    escalation = web_client.post("/parametres/reponse-incidents/escalade")
    assert escalation.status_code == 303 and "escalades=0" in escalation.headers["location"]
    assert web_client.post(
        "/parametres/reponse-incidents/delais/haute", data={"delai_valeur": "2", "delai_unite": "semaines"}
    ).status_code == 422


def test_unknown_pages_show_html_errors_but_api_keeps_json(web_client) -> None:
    missing_incident_page = web_client.get(f"/incidents/{uuid4()}")
    missing_route_page = web_client.get("/page-inexistante")
    missing_incident_api = web_client.get(f"/api/incidents/{uuid4()}")

    assert missing_incident_page.status_code == 404 and "text/html" in missing_incident_page.headers["content-type"]
    assert missing_route_page.status_code == 404 and "text/html" in missing_route_page.headers["content-type"]
    assert missing_incident_api.status_code == 404 and missing_incident_api.json()["error_code"] == "resource_not_found"
    assert web_client.get("/incidents?vue=inconnue").status_code == 422


def test_page_notice_only_shows_known_messages(web_client) -> None:
    assert "Incident créé." in web_client.get("/incidents?notice=incident_cree").text
    assert "texte-injecte" not in web_client.get("/incidents?notice=texte-injecte").text


def test_every_page_shows_the_demo_mode_indicator(web_client) -> None:
    for page_path in ["/", "/incidents", "/alertes", "/journaux"]:
        page = web_client.get(page_path).text
        assert "MODE DÉMONSTRATION" in page and "alert-source-page-demo" in page and "MODE DÉMO" in page


@pytest.mark.parametrize(
    ("is_listening", "expected_mode", "expected_badge"),
    [(True, "live", "EN DIRECT"), (False, "live-inactive", "SYSLOG INACTIF")],
)
def test_real_mode_shows_the_reception_state_instead_of_the_demo_ribbon(
    web_client, monkeypatch, is_listening, expected_mode, expected_badge
) -> None:
    from backend.core.settings import get_application_settings
    from backend.integrations.fortianalyzer import log_source_selection
    from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
        FortiAnalyzerSyslogReceiver,
        SyslogReceptionParameters,
    )

    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    get_application_settings.cache_clear()
    receiver = FortiAnalyzerSyslogReceiver(SyslogReceptionParameters())
    if is_listening:
        # Écoute considérée active, sans ouvrir de port ; l'arrêt de l'application appellera shutdown/server_close.
        receiver._servers = [SimpleNamespace(shutdown=lambda: None, server_close=lambda: None)]
    monkeypatch.setattr(log_source_selection, "_shared_syslog_receiver", receiver if is_listening else None)

    page = web_client.get("/").text

    assert f"alert-source-page-{expected_mode}" in page and expected_badge in page
    assert "MODE DÉMONSTRATION" not in page
