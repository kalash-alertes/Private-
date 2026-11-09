"""Tests de l'interface web : chaque page s'affiche, et les formulaires réalisent les actions métier.

Les pages sont vérifiées par leur code HTTP et la présence de textes clés (pas de comparaison de HTML complet).
Données synthétiques uniquement.
"""

from types import SimpleNamespace
from uuid import uuid4
import re

import pytest

from backend.core.criticality import CriticalityLevel
from backend.core.pagination import PaginationParameters
from backend.core.settings import get_application_settings
from backend.features.audit_journal import service as audit_journal_service
from backend.features.audit_journal.schemas import AuditEventListFilters
from backend.features.incidents import service as incidents_service
from backend.features.incidents import incident_response_checklist
from backend.features.incidents.schemas import IncidentCreationRequest, IncidentListFilters
from backend.features.playbooks import service as playbooks_service
from backend.features.source_logs import service as source_logs_service
from backend.features.import_runs import service as import_runs_service
from tests.synthetic_data import build_synthetic_new_source_log
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
    "/logs-bruts",
    "/logs-bruts?criticite=haute&enregistrement=ecartes&recherche=192.0.2",
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


def test_dashboard_metric_cards_link_to_the_matching_pages(web_client) -> None:
    response = web_client.get("/")

    assert response.status_code == 200
    assert 'href="/incidents?vue=en_cours" aria-label="Voir les incidents ouverts"' in response.text
    assert 'href="/alertes" aria-label="Voir toutes les alertes"' in response.text
    assert 'href="/incidents?vue=traites" aria-label="Voir les incidents traités"' in response.text
    assert "Temps moyen de traitement" in response.text


def test_incident_response_checklist_can_be_completed_and_reopened(web_client, database_session) -> None:
    storage_result = store_synthetic_source_log(database_session, identifier_suffix="response-checklist")
    incident = incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=storage_result.source_log_id)
    )
    checklist = incident_response_checklist.fetch_incident_response_checklist(database_session, incident.id)
    end_test_session_transaction(database_session)

    assert len(checklist) == 7
    assert checklist[0].titre == "Documenter les faits"
    assert checklist[0].description == "Machine, utilisateur, preuve (alerte, inventaire logiciel)."
    incident_page_url = f"/incidents/{incident.id}"
    page_response = web_client.get(incident_page_url)
    assert page_response.status_code == 200
    assert "Plan de réponse conseillé" in page_response.text
    assert "Aide-mémoire générique" in page_response.text

    completion_response = web_client.post(
        f"{incident_page_url}/checklist/{checklist[0].id}",
        data={"terminee": ["non", "oui"], "terminee_par": "analyste.synthetique"},
    )
    assert completion_response.status_code == 303
    completed_page = web_client.get(incident_page_url).text
    assert f'id="checklist-{checklist[0].id}" type="checkbox" name="terminee" value="oui" checked' in completed_page
    assert "analyste.synthetique" in completed_page

    reopening_response = web_client.post(
        f"{incident_page_url}/checklist/{checklist[0].id}",
        data={"terminee": ["non"]},
    )
    assert reopening_response.status_code == 303
    reopened_page = web_client.get(incident_page_url).text
    checkbox = re.search(rf'<input[^>]*id="checklist-{checklist[0].id}"[^>]*>', reopened_page)
    assert checkbox is not None and "checked" not in checkbox.group()


def test_settings_root_redirects_to_incident_response(web_client) -> None:
    response = web_client.get("/parametres")
    assert response.status_code == 303 and response.headers["location"] == "/parametres/reponse-incidents"


def test_static_stylesheets_are_served(web_client) -> None:
    component_stylesheet = web_client.get("/static/css/components.css")
    light_theme = web_client.get("/static/css/pink_theme.css")
    alert_charts = web_client.get("/static/css/alerts.css")
    dashboard_styles = web_client.get("/static/css/dashboard.css")
    incident_styles = web_client.get("/static/css/incidents.css")

    assert component_stylesheet.status_code == 200 and "severity-pill" in component_stylesheet.text
    assert light_theme.status_code == 200 and "body * { color: var(--text) !important; }" in light_theme.text
    assert "--sidebar: #edf2eb" in web_client.get("/static/css/foundation.css").text
    assert alert_charts.status_code == 200 and ".alert-donut-chart" in alert_charts.text
    assert dashboard_styles.status_code == 200 and ".stat-card-link" in dashboard_styles.text
    assert incident_styles.status_code == 200 and ".response-checklist-form" in incident_styles.text


def test_alerts_page_shows_three_severity_groups_and_both_charts(web_client, database_session) -> None:
    for index, criticality in enumerate(CriticalityLevel):
        store_synthetic_source_log(database_session, identifier_suffix=f"severity-{index}", criticite_source=criticality)

    end_test_session_transaction(database_session)
    response = web_client.get("/alertes")

    assert response.status_code == 200
    assert 'class="alert-bar-chart"' in response.text
    assert 'class="alert-donut-chart"' in response.text
    assert "Répartition circulaire" in response.text
    assert "Critique" in response.text and "Moyenne" in response.text and "Faible" in response.text
    assert "Critiques et hautes" in response.text
    # Seuil par défaut `moyenne` : la case Faible signale que ces niveaux ne sont pas collectés.
    assert "Non collectées (seuil : Moyenne et plus)" in response.text
    assert "Source : Haute" in response.text and "Source : Information" in response.text
    assert "2</strong>" in response.text and "5</strong>" in response.text


@pytest.mark.parametrize("raw_fields", [
    {"msg": "<script>alert('test')</script>", "nested": {"srcip": "192.0.2.11"}, "ports": [80, 443]},
    {},
    None,
])
def test_alert_links_to_its_own_original_fields(web_client, database_session, raw_fields) -> None:
    import json
    import html

    import_run = import_runs_service.start_import_run(database_session)
    source_log = build_synthetic_new_source_log(import_run.id, identifier_suffix="original-fields").model_copy(
        update={"donnees_brutes": raw_fields}
    )
    storage = source_logs_service.store_source_log_if_new(database_session, source_log)
    store_synthetic_source_log(database_session, identifier_suffix="other-alert")
    end_test_session_transaction(database_session)
    detail_url = f"/alertes/{storage.source_log_id}"

    assert f'href="{detail_url}"' in web_client.get("/alertes").text
    response = web_client.get(detail_url)

    assert response.status_code == 200
    assert source_log.identifiant_source in response.text and "SYNTHETIQUE-other-alert" not in response.text
    assert "<script>alert(" not in response.text
    if raw_fields is None:
        assert "Aucune donnée brute n'a été conservée" in response.text
    else:
        raw_json = re.search(r'<pre class="raw-log-raw">(.*?)</pre>', response.text, re.S)
        assert raw_json is not None
        assert json.loads(html.unescape(raw_json.group(1))) == raw_fields
    assert "Le texte syslog exact n'est pas conservé en base" in response.text


def test_original_log_links_to_the_matching_incident(web_client, database_session) -> None:
    storage = store_synthetic_source_log(database_session, identifier_suffix="original-with-incident")
    incident = incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=storage.source_log_id)
    )
    end_test_session_transaction(database_session)

    response = web_client.get(f"/alertes/{storage.source_log_id}")

    assert response.status_code == 200
    assert f'href="/incidents/{incident.id}"' in response.text


@pytest.mark.parametrize("log_id, status_code", [(str(uuid4()), 404), ("invalid-uuid", 422)])
def test_original_log_reports_missing_or_invalid_identifier(web_client, log_id, status_code) -> None:
    response = web_client.get(f"/alertes/{log_id}")

    assert response.status_code == status_code and "text/html" in response.headers["content-type"]


def read_alert_summary_card_count(page_html: str, card_class: str) -> int:
    card_match = re.search(rf'<article class="summary-card {card_class}">.*?<strong>([\d\s ]+)</strong>', page_html, re.S)
    assert card_match, card_class
    return int(re.sub(r"\D", "", card_match.group(1)))


def test_live_alert_charts_count_low_logs_without_storing_or_processing_them(
    web_client, database_session, monkeypatch,
) -> None:
    from backend.features.raw_syslog_feed import service as raw_feed_service
    from backend.features.raw_syslog_feed.schemas import RawSyslogFeedStatisticsRead

    store_synthetic_source_log(database_session, identifier_suffix="stored-only")
    end_test_session_transaction(database_session)
    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    get_application_settings.cache_clear()
    statistics = RawSyslogFeedStatisticsRead(
        est_en_mode_demo=False, est_a_l_ecoute=True, severite_minimale=CriticalityLevel.MEDIUM,
        nb_messages_lisibles=1530, nb_messages_enregistrables=15,
        nb_messages_ecartes_par_le_seuil=1515, nb_messages_illisibles=0,
        nb_messages_emetteur_refuse=0, nb_messages_perdus_file_pleine=0,
        nb_datagrammes_udp_perdus_par_le_systeme=0,
        nb_messages_gardes_pour_affichage=2, capacite_affichage=2,
        repartition_par_niveau=[
            dict(niveau_source=label, nombre=count, pourcentage=0, criticite_source=criticality,
                 est_enregistre_par_la_collecte=stored)
            for label, count, criticality, stored in [
                ("error", 10, CriticalityLevel.HIGH, True),
                ("warning", 5, CriticalityLevel.MEDIUM, True),
                ("notice", 1500, CriticalityLevel.LOW, False),
                ("information", 12, CriticalityLevel.INFORMATION, False),
                ("unknown", 3, None, False),
            ]
        ],
    )
    monkeypatch.setattr(raw_feed_service, "read_raw_syslog_statistics", lambda settings: statistics)
    try:
        page = web_client.get("/alertes").text
        assert read_alert_summary_card_count(page, "alert-summary-critical") == 10
        assert read_alert_summary_card_count(page, "alert-summary-medium") == 5
        assert read_alert_summary_card_count(page, "alert-summary-low") == 1512
        assert read_alert_summary_card_count(page, "alert-summary-total") == 1
        assert "1527</text>" in page and "logs reçus</text>" in page
        assert "3 message(s) de niveau inconnu" in page
        assert "non enregistrées" in page and "remis à zéro au redémarrage" in page
        assert page.count('class="incident-title"') == 1
        assert source_logs_service.count_all_source_logs(database_session) == 1
        assert incidents_service.list_incidents(
            database_session, IncidentListFilters(), PaginationParameters(limit=1),
        ).total == 0
        statistics.repartition_par_niveau = []
        statistics.nb_messages_lisibles = 0
        statistics.est_a_l_ecoute = False
        inactive = web_client.get("/alertes").text
        assert read_alert_summary_card_count(inactive, "alert-summary-low") == 0
        assert "Réception syslog inactive" in inactive
    finally:
        get_application_settings.cache_clear()


def test_alerts_page_puts_every_source_level_in_its_severity_case(web_client, database_session) -> None:
    # Effectifs distincts par niveau pour vérifier chaque somme : Critique = critique + haute (3 + 2),
    # Moyenne = moyenne (4), Faible = faible + information (1 + 6).
    log_count_by_level = {
        CriticalityLevel.CRITICAL: 3,
        CriticalityLevel.HIGH: 2,
        CriticalityLevel.MEDIUM: 4,
        CriticalityLevel.LOW: 1,
        CriticalityLevel.INFORMATION: 6,
    }
    for criticality, log_count in log_count_by_level.items():
        for index in range(log_count):
            store_synthetic_source_log(
                database_session, identifier_suffix=f"{criticality.value}-{index}", criticite_source=criticality
            )
    end_test_session_transaction(database_session)

    page = web_client.get("/alertes").text

    assert read_alert_summary_card_count(page, "alert-summary-critical") == 5
    assert read_alert_summary_card_count(page, "alert-summary-medium") == 4
    assert read_alert_summary_card_count(page, "alert-summary-low") == 7
    assert read_alert_summary_card_count(page, "alert-summary-total") == 16
    # Chaque ligne : pastille de la case, et rappel du niveau source quand il est regroupé.
    rows = re.findall(r"<tr>\s*<td>\s*<div class=\"incident-title\">.*?</tr>", page, re.S)
    assert len(rows) == 16
    pills = [re.search(r'aria-label="Niveau (\w+)"', row).group(1) for row in rows]
    assert (pills.count("Critique"), pills.count("Moyenne"), pills.count("Faible")) == (5, 4, 7)
    assert page.count("Source : Haute") == 2 and page.count("Source : Information") == 6
    # Le filtre par niveau source fonctionne pour chaque niveau.
    for criticality, log_count in log_count_by_level.items():
        filtered_page = web_client.get(f"/alertes?criticite={criticality.value}").text
        assert f'<span class="table-count">{log_count}</span>' in filtered_page, criticality


def test_low_case_is_labelled_normally_when_every_level_is_collected(web_client, monkeypatch) -> None:
    monkeypatch.setenv("LOG_COLLECTION_MINIMUM_CRITICALITY", "information")
    get_application_settings.cache_clear()
    try:
        page = web_client.get("/alertes").text
    finally:
        get_application_settings.cache_clear()

    assert "Faibles et informatives" in page and "Non collectées" not in page


def test_alert_type_groups_include_all_types_and_paginate_within_the_selected_type(
    web_client, database_session,
) -> None:
    for index in range(27):
        store_synthetic_source_log(
            database_session, identifier_suffix=f"vpn-{index:02}", event_type="vpn",
        )
    forward_log = store_synthetic_source_log(
        database_session, identifier_suffix="forward", event_type="forward",
        criticite_source=CriticalityLevel.MEDIUM,
    )
    incident = incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=forward_log.source_log_id),
    )
    end_test_session_transaction(database_session)

    page = web_client.get("/alertes").text
    groups = re.findall(r'<details class="alert-type-group".*?</details>', page, re.S)
    assert len(groups) == 2
    vpn_group, forward_group = groups
    assert '<span class="alert-type-name">forward</span>' in forward_group
    assert '<span class="table-count">1</span>' in forward_group
    assert f'href="/incidents/{incident.id}"' in forward_group
    assert '<span class="alert-type-name">vpn</span>' in vpn_group
    assert '<span class="table-count">27</span>' in vpn_group
    assert vpn_group.count('class="incident-title"') == 25
    assert "SYNTHETIQUE-forward" not in vpn_group
    assert 'href="/alertes?groupe=vpn&offset=25"' in vpn_group
    assert not re.search(r'<details[^>]*\bopen\b', page)

    next_page = web_client.get("/alertes?groupe=vpn&offset=25").text
    next_groups = re.findall(r'<details class="alert-type-group".*?</details>', next_page, re.S)
    assert next_groups[0].startswith('<details class="alert-type-group" open>')
    assert next_groups[0].count('class="incident-title"') == 2
    first_ids = set(re.findall(r'SYNTHETIQUE-vpn-\d+', vpn_group))
    last_ids = set(re.findall(r'SYNTHETIQUE-vpn-\d+', next_groups[0]))
    assert len(first_ids | last_ids) == 27 and not first_ids & last_ids
    assert "SYNTHETIQUE-forward" in next_groups[1]
    assert 'href="/alertes?groupe=vpn&offset=0"' in next_groups[0]

    filtered = web_client.get("/alertes?criticite=critique").text
    assert '<span class="alert-type-name">forward</span>' not in filtered
    assert '<span class="table-count">27</span>' in filtered
    assert 'groupe=vpn&amp;criticite=critique&offset=25' in filtered


def test_alert_type_groups_sort_by_filtered_counts_then_type(web_client, database_session) -> None:
    for index, (event_type, criticality) in enumerate([
        ("vpn", CriticalityLevel.CRITICAL),
        ("vpn", CriticalityLevel.MEDIUM),
        ("vpn", CriticalityLevel.MEDIUM),
        ("forward", CriticalityLevel.CRITICAL),
        ("forward", CriticalityLevel.CRITICAL),
        ("ips", CriticalityLevel.CRITICAL),
    ]):
        store_synthetic_source_log(
            database_session, identifier_suffix=f"sorted-{index}", event_type=event_type,
            criticite_source=criticality,
        )
    end_test_session_transaction(database_session)
    assert re.findall(
        r'<span class="alert-type-name">(.*?)</span>', web_client.get("/alertes").text,
    ) == ["vpn", "forward", "ips"]
    assert re.findall(
        r'<span class="alert-type-name">(.*?)</span>', web_client.get("/alertes?criticite=critique").text,
    ) == ["forward", "ips", "vpn"]


def test_alert_type_groups_escape_names_and_keep_exact_types_separate(web_client, database_session) -> None:
    for index, event_type in enumerate(["vpn", "VPN", 'test <script> & " /']):
        store_synthetic_source_log(
            database_session, identifier_suffix=f"type-{index}", event_type=event_type,
        )
    end_test_session_transaction(database_session)
    page = web_client.get("/alertes").text
    assert page.count('<details class="alert-type-group"') == 3
    assert '<span class="alert-type-name">VPN</span>' in page
    assert '<span class="alert-type-name">vpn</span>' in page
    assert '<script>' not in page
    assert 'test &lt;script&gt; &amp; &#34; /' in page
    assert web_client.get("/alertes?criticite=faible").text.count('<details class="alert-type-group"') == 0
    assert web_client.get("/alertes?offset=-1").status_code == 422
    assert web_client.get("/alertes?groupe=" + "x" * 256).status_code == 422


def test_dashboard_uses_global_theme_and_shows_alert_source(web_client) -> None:
    """Le dashboard suit le thème sauge commun (plus de thème noir/blanc dédié) et garde l'indicateur de source."""
    dashboard = web_client.get("/").text

    assert "pink_theme.css" in dashboard and "dashboard.css" in dashboard
    assert "dashboard_theme" not in dashboard and "data-dashboard-theme" not in dashboard
    assert 'class="source-context alert-source-' in dashboard
    assert web_client.get("/static/css/dashboard_theme.css").status_code == 404


def test_dashboard_keeps_live_incident_data_and_links(web_client, database_session) -> None:
    playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    storage_result = store_synthetic_source_log(database_session)
    end_test_session_transaction(database_session)
    incident_location = web_client.post("/incidents", data={"log_id": str(storage_result.source_log_id)}).headers["location"]

    dashboard = web_client.get("/").text

    assert "INC-000001" in dashboard
    assert incident_location.split("?")[0] in dashboard
    assert 'href="/incidents?vue=traites"' in dashboard
    assert "Activité des alertes" in dashboard and "Répartition par sévérité" in dashboard


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


def test_raw_logs_page_shows_live_messages_and_their_fields(web_client, monkeypatch) -> None:
    from backend.integrations.fortianalyzer import log_source_selection
    from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
        FortiAnalyzerSyslogReceiver,
        SyslogReceptionParameters,
    )

    monkeypatch.setenv("APP_IS_IN_DEMO", "false")
    get_application_settings.cache_clear()
    receiver = FortiAnalyzerSyslogReceiver(SyslogReceptionParameters())
    receiver.handle_received_text(
        '<187>devname="FGT-SYNTHETIQUE" subtype="vpn" level="error" logdesc="IPsec phase 1 error" msg="<b>x</b>"',
        "192.0.2.104",
        "UDP",
    )
    monkeypatch.setattr(log_source_selection, "_shared_syslog_receiver", receiver)

    page = web_client.get("/logs-bruts").text
    update = web_client.get("/logs-bruts/nouveaux?apres=0").text
    nothing_new = web_client.get("/logs-bruts/nouveaux?apres=1").text

    assert "IPsec phase 1 error" in page and "FGT-SYNTHETIQUE" in page and "enregistré" in page
    assert "raw_syslog_feed.js" in page and 'data-last-number="1"' in page
    # Le texte des logs est échappé : aucun HTML venant d'un log n'est interprété.
    assert "<b>x</b>" not in page and "&lt;b&gt;x&lt;/b&gt;" in page
    assert 'data-new-count="1"' in update and 'data-new-count="0"' in nothing_new


def test_raw_logs_filters_are_combined_and_preserved_in_live_updates(web_client, monkeypatch) -> None:
    from tests.features.raw_syslog_feed.test_raw_syslog_feed_service import (
        ERROR_MESSAGE, NOTICE_MESSAGE, install_receiver_with_messages,
    )

    install_receiver_with_messages(monkeypatch, NOTICE_MESSAGE, ERROR_MESSAGE, "illisible")
    query = "criticite=haute&enregistrement=enregistres&recherche=IPSEC"
    page = web_client.get(f"/logs-bruts?{query}").text
    update = web_client.get(f"/logs-bruts/nouveaux?apres=0&{query}").text

    assert 'data-number="2"' in page and 'data-number="1"' not in page and 'data-number="3"' not in page
    assert 'value="haute" selected' in page and 'value="enregistres" selected' in page
    assert 'data-update-url="/logs-bruts/nouveaux?criticite=haute&amp;enregistrement=enregistres&amp;recherche=IPSEC"' in page
    assert 'data-number="2"' in update and 'data-new-count="1"' in update
    assert 'data-new-count="0"' in web_client.get(f"/logs-bruts/nouveaux?apres=2&{query}").text
    reset_page = web_client.get("/logs-bruts?criticite=&enregistrement=tous&recherche=").text
    assert all(f'data-number="{number}"' in reset_page for number in (1, 2, 3))



def test_playbook_files_are_synchronized_from_the_playbooks_page(web_client) -> None:
    import json

    from backend.features.playbooks.playbook_files import get_playbook_files_directory

    directory = get_playbook_files_directory()
    (directory / "nouveau.json").write_text(
        json.dumps({"nom": "Playbook fichier synthétique", "source": "Source synthétique",
                    "etapes": [{"titre": "Étape A"}]}),
        encoding="utf-8",
    )
    response = web_client.post("/parametres/playbooks/synchroniser")
    assert response.status_code == 303 and "playbooks_synchronises" in response.headers["location"]
    assert "Playbook fichier synthétique" in web_client.get(response.headers["location"]).text

    (directory / "invalide.json").write_text('{"nom": "Sans source", "etapes": []}', encoding="utf-8")
    refused = web_client.post("/parametres/playbooks/synchroniser")
    assert refused.status_code == 422 and "invalide.json" in refused.text
