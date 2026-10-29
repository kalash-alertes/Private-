"""Tests des routes HTTP de consultation de l'historique des imports."""

from uuid import uuid4

from backend.features.import_runs import service as import_runs_service
from backend.features.import_runs.schemas import ImportRunFinishedOutcome


def test_import_runs_are_listed_with_pagination_metadata(api_client, database_session) -> None:
    import_run = import_runs_service.start_import_run(database_session)
    import_runs_service.finish_import_run(
        database_session,
        import_run.id,
        ImportRunFinishedOutcome(statut="echouee", nb_logs_recus=0, nb_logs_inseres=0, nb_logs_ignores=0, erreur="ko"),
    )

    response = api_client.get("/executions-import", params={"limit": 10, "statut": "echouee"})

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (1, 10, 0)
    assert body["items"][0]["id"] == str(import_run.id)
    assert body["items"][0]["erreur"] == "ko"


def test_import_run_detail_and_missing_import_run(api_client, database_session) -> None:
    import_run = import_runs_service.start_import_run(database_session)

    assert api_client.get(f"/executions-import/{import_run.id}").json()["statut"] == "en_cours"
    missing_response = api_client.get(f"/executions-import/{uuid4()}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "resource_not_found"


def test_invalid_query_parameters_are_rejected(api_client) -> None:
    assert api_client.get("/executions-import", params={"limit": 0}).status_code == 422
    assert api_client.get("/executions-import", params={"limit": 201}).status_code == 422
    assert api_client.get("/executions-import", params={"statut": "inconnu"}).status_code == 422
    assert api_client.get("/executions-import/pas-un-uuid").status_code == 422


def test_import_runs_cannot_be_created_through_http(api_client) -> None:
    # Démarrer / terminer une exécution est réservé au collecteur interne.
    assert api_client.post("/executions-import", json={}).status_code == 405
