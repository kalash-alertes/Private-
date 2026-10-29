"""Tests des routes HTTP de consultation des logs (données synthétiques)."""

from uuid import uuid4

from tests.synthetic_data import store_synthetic_source_log


def test_logs_list_exposes_metadata_without_raw_data(api_client, database_session) -> None:
    storage_result = store_synthetic_source_log(database_session)

    response = api_client.get("/logs", params={"criticite_source": "critique"})

    assert response.status_code == 200
    listed_log = response.json()["items"][0]
    assert listed_log["id"] == str(storage_result.source_log_id)
    assert listed_log["identifiant_source"].startswith("SYNTHETIQUE-")
    assert "donnees_brutes" not in listed_log
    assert listed_log["date_evenement"].endswith(("Z", "+00:00"))


def test_log_detail_includes_raw_data_and_missing_log_returns_404(api_client, database_session) -> None:
    storage_result = store_synthetic_source_log(database_session)

    detail_response = api_client.get(f"/logs/{storage_result.source_log_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["donnees_brutes"]["origine"] == "donnees_synthetiques_de_test"
    assert api_client.get(f"/logs/{uuid4()}").status_code == 404


def test_invalid_log_filters_are_rejected(api_client) -> None:
    assert api_client.get("/logs", params={"criticite_source": "inconnue"}).status_code == 422
    # Date sans fuseau horaire : ambiguë, refusée.
    assert api_client.get("/logs", params={"date_evenement_min": "2026-10-01T08:00:00"}).status_code == 422
    inverted_range_response = api_client.get(
        "/logs",
        params={"date_evenement_min": "2026-10-02T00:00:00Z", "date_evenement_max": "2026-10-01T00:00:00Z"},
    )
    assert inverted_range_response.status_code == 422


def test_there_is_no_public_ingestion_route(api_client) -> None:
    assert api_client.post("/logs", json={"identifiant_source": "SYNTHETIQUE-x"}).status_code == 405
