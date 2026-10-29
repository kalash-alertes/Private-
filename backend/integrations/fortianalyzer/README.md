# Intégration `fortianalyzer`

**Rôle** : fournir les alertes à la collecte (`backend/features/log_collection`), depuis deux sources interchangeables
qui respectent le même contrat (`critical_log_source.py`) :

| Fichier | Rôle |
|---|---|
| `critical_log_source.py` | Le contrat `CriticalLogSource` (`fetch_logs_between`) |
| `fortianalyzer_json_rpc_client.py` | Le vrai client : API JSON-RPC (connexion ou jeton, recherche LogView, pages, déconnexion) |
| `fortianalyzer_api_schemas.py` | Validation Pydantic des réponses de FortiAnalyzer |
| `demo_log_source.py` | Source de démonstration (logs inventés au format FortiAnalyzer) |
| `log_source_selection.py` | Choix de la source selon `APP_IS_IN_DEMO` ; liste des réglages manquants |
| `fortianalyzer_errors.py` | Erreurs (configuration, connexion, API) — messages sans secret |

Aucune règle métier ici (pas de seuil de sévérité, pas d'enregistrement) : c'est le rôle de `log_collection`.

**Tester** : `python -m pytest tests/integrations` (faux serveur, aucun appel réseau).

**Doc** : [docs/technical/log_collection.md](../../../docs/technical/log_collection.md).
