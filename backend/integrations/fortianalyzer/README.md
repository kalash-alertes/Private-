# Intégration `fortianalyzer`

**Rôle** : fournir les alertes à la collecte (`backend/features/log_collection`), depuis deux sources interchangeables
qui respectent le même contrat (`critical_log_source.py`). En mode réel, FortiAnalyzer **envoie** ses logs par syslog :
l'application écoute un port (UDP/TCP, 5140 par défaut) ; aucune API n'est interrogée.

| Fichier | Rôle |
|---|---|
| `critical_log_source.py` | Le contrat `CriticalLogSource` (`take_new_logs`) ; nom du champ des métadonnées de réception |
| `fortianalyzer_syslog_receiver.py` | La vraie source : écoute syslog UDP/TCP, filtre des émetteurs, file d'attente en mémoire |
| `fortianalyzer_syslog_message_parser.py` | Validation Pydantic d'un message reçu et lecture des champs Fortinet `clé=valeur` |
| `demo_log_source.py` | Source de démonstration (logs inventés au format FortiAnalyzer) |
| `log_source_selection.py` | Choix de la source selon `APP_IS_IN_DEMO` ; démarrage/arrêt du récepteur partagé ; réglages invalides |
| `fortianalyzer_errors.py` | Erreurs (configuration, réception inactive) — messages sans secret |

Aucune règle métier ici (pas de seuil de sévérité, pas d'enregistrement) : c'est le rôle de `log_collection`.

**Tester** : `python -m pytest tests/integrations` (aucun appel réseau externe ; les tests de sockets n'utilisent que
127.0.0.1).

**Doc** : [docs/technical/log_collection.md](../../../docs/technical/log_collection.md).
