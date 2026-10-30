# Feature `log_collection`

**Rôle** : enregistrer les alertes dans la base — celles **transférées par FortiAnalyzer en syslog**
(`APP_IS_IN_DEMO=false`, file d'attente vidée à chaque collecte) ou celles d'une **source de démonstration**
(`APP_IS_IN_DEMO=true`). Chaque collecte qui reçoit quelque chose est une exécution de l'historique des imports
(page Journaux). Démarre et arrête l'écoute syslog avec l'application. Aucune table propre.

**Fichiers**
- `service.py` : une collecte complète (conversion, seuil de sévérité, enregistrement sans doublon, bilan) ;
  `start_log_reception` / `stop_log_reception` ; description de la configuration et de l'état de l'écoute
- `fortianalyzer_log_normalizer.py` : log FortiAnalyzer → log de l'application (sévérité, date, type, empreinte)
- `collection_scheduler.py` : collecte automatique toutes les `LOG_COLLECTION_INTERVAL_SECONDS` secondes
- `schemas.py` · `router.py` (`POST /api/collecte`, `GET /api/collecte/configuration`)

**Dépend de** : `import_runs` et `source_logs` (services publics), `backend/integrations/fortianalyzer` (sources).

**Tester** : `python -m pytest tests/features/log_collection tests/integrations`.

**Doc** : [docs/technical/log_collection.md](../../../docs/technical/log_collection.md).
