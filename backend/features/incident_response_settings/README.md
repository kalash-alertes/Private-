# Feature `incident_response_settings`

**Rôle** : Paramètres > Réponse aux incidents : délai de traitement et escalade automatique **par criticité**
(table `delais_reponse_incidents`, 5 lignes créées par la migration 0003 avec des valeurs par défaut à ajuster).

**Fichiers** : `models.py` · `schemas.py` · `repository.py` · `service.py` · `router.py`
(`GET /api/parametres/reponse-incidents/delais`, `PUT .../delais/{criticite}`).

**Fonction publique** (utilisée par `incidents`) : `fetch_response_deadline_rules_by_criticality`.
L'escalade elle-même est exécutée par `incidents/automatic_escalation.py` (elle modifie des incidents).

**Tester** : `python -m pytest tests/features/incident_response_settings`.

**Doc** : [docs/technical/incident_response_settings.md](../../../docs/technical/incident_response_settings.md).
