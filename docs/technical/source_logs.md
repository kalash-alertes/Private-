# Fonctionnalité `source_logs` — logs connus de l'application

Code : `backend/features/source_logs/`. Table : `logs` (voir [database.md](./database.md)).

## Rôle

Conserver les métadonnées des logs critiques collectés, sans doublon, et les exposer en consultation.
**Aucune route HTTP d'ingestion** : l'enregistrement est réservé au futur collecteur, via le service.

## Fonctions publiques (`service.py`)

| Fonction | Effet | Erreurs |
|---|---|---|
| `store_source_log_if_new(session, NewSourceLogData)` | insère si `identifiant_source` inconnu, sinon ne touche à rien ; commit ; retourne `SourceLogStorageResult(source_log_id, was_inserted)` | `ResourceNotFoundError` / `ResourceConflictError` si l'exécution d'import est absente / terminée |
| `fetch_source_log_metadata(session, id)` | métadonnées (utilisée par `incidents`) | `ResourceNotFoundError` |
| `fetch_source_log_detail`, `list_source_logs` | consultation | `ResourceNotFoundError` |

## Validation des données entrantes (`NewSourceLogData`)

- `identifiant_source`, `type` : texte non vide (espaces retirés), ≤ 255 caractères.
- `date_evenement` : **doit avoir un fuseau horaire** (sinon refus), convertie en UTC.
- `criticite_source` : un des niveaux provisoires de `backend/core/criticality.py`.
- `donnees_brutes` (objet JSON, facultatif), `reference_opensearch` (facultatif), `execution_import_id` (obligatoire).
- Champ inconnu ⇒ refus (`extra="forbid"`).

La traduction des champs FortiAnalyzer vers ce schéma (normalisation) n'existe pas encore : elle dépend de l'API réelle.

## Idempotence et concurrence

`repository.insert_source_log_unless_source_identifier_exists` utilise
`INSERT ... ON CONFLICT (identifiant_source) DO NOTHING RETURNING id` (PostgreSQL et SQLite).

- Rejouer le même log (nouvelle tentative, import suivant) ⇒ `was_inserted=False`, même id, aucune modification.
- Deux collecteurs simultanés ⇒ la base arbitre : un seul insère, l'autre reçoit `False` sans erreur ni rollback
  (test PostgreSQL `test_concurrent_imports_of_the_same_log_store_it_once`).
- Le log existant garde **son exécution d'origine** et **sa criticité source**, même si le doublon reçu diffère.
  Conséquence : une éventuelle mise à jour côté FortiAnalyzer d'un même événement n'est pas répercutée (à décider si besoin).

## Routes HTTP

Fonctions publiques ajoutées pour le tableau de bord et les incidents : `fetch_source_logs_metadata_by_ids`,
`count_all_source_logs`, `count_source_logs_per_event_day` (agrégation par jour UTC en Python).


| Méthode | Route | Réponse |
|---|---|---|
| GET | `/api/logs?criticite_source=&type=&execution_import_id=&date_evenement_min=&date_evenement_max=&limit=&offset=` | page de **métadonnées** (sans `donnees_brutes`), événements les plus récents d'abord |
| GET | `/api/logs/{id}` | détail **avec** `donnees_brutes`, 404 si absent |

Dates de filtre : bornes incluses, fuseau obligatoire (sinon 422) ; plage inversée ⇒ 422. POST ⇒ 405.

## Points ouverts

- Stockage du log brut (PostgreSQL, OpenSearch, ou les deux) non décidé : `donnees_brutes` reste facultatif.
- `donnees_brutes` peut contenir des données sensibles et est exposé par `/logs/{id}` **sans authentification**.
