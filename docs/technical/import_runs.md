# Fonctionnalité `import_runs` — historique des imports

Code : `backend/features/import_runs/`. Table : `executions_import` (voir [database.md](./database.md)).

## Rôle

Tracer chaque tentative de collecte FortiAnalyzer : début, fin, statut, compteurs, erreur, curseur de reprise.
Seul le code interne (futur collecteur) démarre et termine une exécution ; l'API HTTP ne fait que consulter.

## Fonctions publiques (`service.py`)

| Fonction | Effet | Erreurs |
|---|---|---|
| `start_import_run(session)` | crée une exécution `en_cours`, commit | — |
| `finish_import_run(session, id, ImportRunFinishedOutcome)` | statut final + compteurs + erreur nettoyée + curseur ; `fin = now()` (horloge DB), commit | `ResourceNotFoundError`, `ResourceConflictError` si déjà terminée |
| `ensure_import_run_accepts_new_logs(session, id)` | vérifie que l'exécution existe et est `en_cours` (utilisée par `source_logs`) | idem |
| `fetch_import_run`, `list_import_runs` | consultation | `ResourceNotFoundError` |

## Définition des compteurs

- `nb_logs_recus` : logs renvoyés par la source pendant l'exécution.
- `nb_logs_inseres` : logs **nouveaux** réellement enregistrés (`was_inserted=True` renvoyé par `store_source_log_if_new`).
- `nb_logs_ignores` : logs déjà connus (doublons), non recréés.
- `recus - inseres - ignores` = logs **rejetés** (invalides, ou non enregistrés suite à une erreur).

Le collecteur calcule ces compteurs à partir des résultats réels de `store_source_log_if_new`, pas du nombre de requêtes.

## Règles de cohérence (validées par `ImportRunFinishedOutcome` **et** par des CHECK en base, migration 0002)

| Règle | Où |
|---|---|
| compteurs ≥ 0 ; `inseres + ignores ≤ recus` | schéma + CHECK |
| `reussie` ⇒ aucune erreur **et** aucun log rejeté (`inseres + ignores = recus`) | schéma (+ CHECK pour « aucune erreur ») |
| `partielle` / `echouee` ⇒ message d'erreur non vide | schéma + CHECK |
| `fin` NULL ⇔ `en_cours` ; `fin ≥ debut` | CHECK |
| une exécution terminée n'est jamais réécrite | service (409) |
| aucun log ne peut être rattaché à une exécution terminée | service `source_logs` (409) |

## Erreurs sans secrets

`error_message_sanitizer.py` masque les motifs connus (identifiants dans une URL, `Authorization`, `Bearer`, `password=`,
`token`, `api_key`, `session`...) et tronque à 2000 caractères. `build_import_error_message_from_exception(exc)` produit
`TypeException: message` déjà nettoyé. **Filet de sécurité seulement** : le collecteur ne doit jamais construire un
message contenant un secret.

## Concurrence

`finish_import_run` charge l'exécution avec `SELECT ... FOR UPDATE` : deux fins simultanées sont sérialisées ; la seconde
voit l'exécution terminée et reçoit un conflit (test PostgreSQL `test_concurrent_finishes_of_one_import_run_keep_the_first_outcome`).

Cas limite connu : `ensure_import_run_accepts_new_logs` ne verrouille pas l'exécution. Un log enregistré **pendant** que
la même exécution est terminée par un autre processus pourrait être rattaché juste après la fin. En pratique le collecteur
enregistre ses logs puis termine son exécution dans le même fil ; à revoir si la collecte devient parallèle.

## Point de reprise

`service.fetch_latest_synchronization_cursor` renvoie le `curseur_synchronisation` de la plus récente exécution
**réussie ou partielle** (utilisé par `log_collection` : date ISO de fin de la période lue). Une exécution échouée
n'avance jamais le point de reprise.

## Routes HTTP

| Méthode | Route | Réponse |
|---|---|---|
| GET | `/api/executions-import?statut=&limit=&offset=` | page `{items, total, limit, offset}`, plus récentes d'abord (`debut` desc, puis `id`) |
| GET | `/api/executions-import/{id}` | détail, 404 si absente |

Pas de POST/PUT : 405.

## Tests

`tests/features/import_runs/` (SQLite), `tests/postgresql_integration/` (concurrence, PostgreSQL réel).
