"""Tests des routes HTTP des incidents : parcours complet et codes d'erreur (données synthétiques)."""

from uuid import uuid4

from tests.synthetic_data import store_synthetic_source_log


def create_incident_through_http(api_client, database_session, identifier_suffix="0001") -> dict:
    storage_result = store_synthetic_source_log(database_session, identifier_suffix)
    response = api_client.post("/incidents", json={"log_id": str(storage_result.source_log_id)})
    assert response.status_code == 201
    return response.json()


def test_incident_full_lifecycle_through_http(api_client, database_session) -> None:
    incident = create_incident_through_http(api_client, database_session)
    incident_url = f"/incidents/{incident['id']}"

    assert api_client.put(f"{incident_url}/assignation", json={"assigne_a": "analyste.synthetique"}).status_code == 200
    assert api_client.put(f"{incident_url}/statut", json={"statut": "en_cours"}).status_code == 200
    assert api_client.put(f"{incident_url}/criticite-actuelle", json={"criticite_actuelle": "faible"}).status_code == 200
    qualification_response = api_client.put(
        f"{incident_url}/faux-positif", json={"faux_positif": True, "justification": "Test d'intrusion autorisé"}
    )
    assert qualification_response.status_code == 200
    closed_incident = api_client.put(f"{incident_url}/statut", json={"statut": "cloture"}).json()

    assert closed_incident["statut"] == "cloture" and closed_incident["closed_at"] is not None
    assert closed_incident["criticite_actuelle"] == "faible"
    assert closed_incident["criticite_source"] == "critique"
    assert closed_incident["assigne_a"] == "analyste.synthetique"
    assert closed_incident["faux_positif"] is True
    assert api_client.get(incident_url).json() == closed_incident
    # La criticité source du log reste celle de la source.
    assert api_client.get(f"/logs/{incident['log_id']}").json()["criticite_source"] == "critique"


def test_incident_creation_errors(api_client, database_session) -> None:
    incident = create_incident_through_http(api_client, database_session)

    duplicate_response = api_client.post("/incidents", json={"log_id": incident["log_id"]})
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error_code"] == "resource_conflict"
    assert api_client.post("/incidents", json={"log_id": str(uuid4())}).status_code == 404
    assert api_client.post("/incidents", json={"log_id": "pas-un-uuid"}).status_code == 422
    assert api_client.post("/incidents", json={"log_id": incident["log_id"], "statut": "cloture"}).status_code == 422


def test_incident_action_validation_and_conflict_errors(api_client, database_session) -> None:
    incident_url = f"/incidents/{create_incident_through_http(api_client, database_session)['id']}"

    assert api_client.put(f"{incident_url}/statut", json={"statut": "inconnu"}).status_code == 422
    assert api_client.put(f"{incident_url}/criticite-actuelle", json={"criticite_actuelle": "x"}).status_code == 422
    assert api_client.put(f"{incident_url}/faux-positif", json={"faux_positif": True}).status_code == 422
    assert api_client.put(f"{incident_url}/assignation", json={"assigne_a": ""}).status_code == 422
    assert api_client.put(f"/incidents/{uuid4()}/statut", json={"statut": "en_cours"}).status_code == 404

    api_client.put(f"{incident_url}/statut", json={"statut": "cloture"})
    closed_response = api_client.put(f"{incident_url}/assignation", json={"assigne_a": "analyste.synthetique"})
    assert closed_response.status_code == 409


def test_incidents_list_with_filters_and_pagination(api_client, database_session) -> None:
    first_incident = create_incident_through_http(api_client, database_session, "0001")
    create_incident_through_http(api_client, database_session, "0002")
    api_client.put(f"/incidents/{first_incident['id']}/statut", json={"statut": "en_attente"})

    filtered_body = api_client.get("/incidents", params={"statut": "en_attente"}).json()
    paginated_body = api_client.get("/incidents", params={"limit": 1, "offset": 1}).json()

    assert filtered_body["total"] == 1 and filtered_body["items"][0]["id"] == first_incident["id"]
    assert paginated_body["total"] == 2 and len(paginated_body["items"]) == 1
    assert api_client.get("/incidents", params={"faux_positif": "peut-etre"}).status_code == 422
