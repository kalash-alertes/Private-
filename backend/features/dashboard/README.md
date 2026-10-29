# Feature `dashboard`

**Rôle** : indicateurs du tableau de bord (incidents ouverts/traités, délais dépassés, alertes à traiter, temps moyen
de traitement, répartition par criticité, activité quotidienne). Aucune table : assemble les services publics de
`source_logs` (`count_all_source_logs`, `count_source_logs_per_event_day`) et `incidents`
(`incident_statistics.compute_incident_statistics`).

**Fichiers** : `schemas.py` · `service.py` · `router.py` (`GET /api/tableau-de-bord?nombre_jours=7`).

**Tester** : `python -m pytest tests/features/dashboard`.

**Doc** : [docs/technical/dashboard.md](../../../docs/technical/dashboard.md). Suivre [AGENTS.md](../../../AGENTS.md).
