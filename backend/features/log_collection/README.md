# Feature `log_collection`

**Rôle** : récupérer les alertes et les enregistrer dans la base — depuis le **vrai FortiAnalyzer**
(`APP_IS_IN_DEMO=false`) ou depuis une **source de démonstration** (`APP_IS_IN_DEMO=true`). Chaque passage est une
exécution de l'historique des imports (page Journaux). Aucune table propre.

**Fichiers**
- `service.py` : une collecte complète (période, conversion, seuil de sévérité, enregistrement sans doublon, bilan)
- `fortianalyzer_log_normalizer.py` : log FortiAnalyzer → log de l'application (sévérité, date, type, empreinte)
- `collection_scheduler.py` : collecte automatique toutes les `LOG_COLLECTION_INTERVAL_SECONDS` secondes
- `schemas.py` · `router.py` (`POST /api/collecte`, `GET /api/collecte/configuration`)

**Dépend de** : `import_runs` et `source_logs` (services publics), `backend/integrations/fortianalyzer` (sources).

**Tester** : `python -m pytest tests/features/log_collection tests/integrations`.

**Doc** : [docs/technical/log_collection.md](../../../docs/technical/log_collection.md).
