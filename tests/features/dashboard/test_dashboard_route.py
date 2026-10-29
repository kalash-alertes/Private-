"""Tests de la route du tableau de bord (les calculs sont testés dans tests/features/incidents/test_incident_tracking.py)."""


def test_dashboard_route_returns_indicators_and_daily_activity(api_client) -> None:
    response = api_client.get("/tableau-de-bord?nombre_jours=3")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["nombre_incidents_ouverts"] == 0 and dashboard["temps_moyen_traitement_minutes"] is None
    assert len(dashboard["activite"]) == 3
    assert api_client.get("/tableau-de-bord?nombre_jours=0").status_code == 422
