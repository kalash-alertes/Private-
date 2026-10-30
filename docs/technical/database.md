# Base de données PostgreSQL (V1)

Schéma géré par Alembic : [0001_create_initial_tables.py](../../db/migrations/versions/0001_create_initial_tables.py), [0002_add_consistency_constraints.py](../../db/migrations/versions/0002_add_consistency_constraints.py), [0003_add_settings_playbooks_audit_journal.py](../../db/migrations/versions/0003_add_settings_playbooks_audit_journal.py). Modèles : `backend/features/*/models.py`.
Conventions : clés UUID, dates `TIMESTAMPTZ` (UTC), noms de contraintes préfixés (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).

```mermaid
erDiagram
    executions_import ||--o{ logs : "importe"
    logs ||--o| incidents : "peut déclencher"
    playbooks ||--|{ etapes_playbook : "contient"
    playbooks |o--o{ incidents : "guide"
    incidents ||--o{ etapes_realisees_incident : "avance"
    etapes_playbook ||--o{ etapes_realisees_incident : "cochée dans"
```

Tables sans lien : `delais_reponse_incidents` (une règle par criticité), `journal_audit` (référence libre
`type_ressource` + `identifiant_ressource`, sans clé étrangère pour survivre à la suppression de la ressource).

## `executions_import` (feature `import_runs`)

Une ligne par tentative de collecte.

| Colonne | Type | Règle |
|---|---|---|
| `id` | UUID PK | |
| `debut` / `fin` | timestamptz | `fin` est NULL **si et seulement si** `statut = 'en_cours'` ; `fin ≥ debut` ; `debut` indexé |
| `statut` | text | `en_cours`, `reussie`, `partielle`, `echouee` |
| `nb_logs_recus`, `nb_logs_inseres`, `nb_logs_ignores` | int | ≥ 0 ; `ignores` = doublons déjà connus ; `inseres + ignores ≤ recus` |
| `erreur` | text | détail sans secrets ; obligatoire (non vide) si `partielle`/`echouee`, NULL si `reussie` |
| `curseur_synchronisation` | text | point de reprise (nature dépendante de l'API FortiAnalyzer) |
| `created_at` | timestamptz | |

## `logs` (feature `source_logs`)

| Colonne | Type | Règle |
|---|---|---|
| `id` | UUID PK | |
| `identifiant_source` | varchar(255) | **UNIQUE**, obligatoire, non vide : clé de déduplication |
| `date_evenement` | timestamptz | indexée |
| `type` | varchar(255) | |
| `criticite_source` | varchar(32) | valeur FortiAnalyzer, jamais modifiée ; indexée ; CHECK sur les niveaux |
| `donnees_brutes` | JSONB | optionnel (stratégie de stockage à décider) |
| `reference_opensearch` | varchar(255) | optionnel |
| `arrivee_db` | timestamptz | |
| `execution_import_id` | UUID FK → `executions_import` | première exécution ayant enregistré le log ; `RESTRICT` |

Un log retrouvé lors d'un import ultérieur n'est pas recréé : il incrémente `nb_logs_ignores`.

## `incidents` (feature `incidents`)

| Colonne | Type | Règle |
|---|---|---|
| `id` | UUID PK | |
| `log_id` | UUID FK → `logs` | **UNIQUE** : un incident maximum par log en V1 |
| `statut` | varchar(32) | `nouveau`, `en_cours`, `en_attente`, `resolu`, `cloture` (provisoire) ; indexé |
| `criticite_actuelle` | varchar(32) | réévaluée par l'équipe ; initialisée avec `criticite_source` ; indexée |
| `faux_positif` | bool | si vrai, `justification` non vide obligatoire (CHECK) |
| `justification` | text | |
| `assigne_a` | varchar(255) | texte libre provisoire ; NULL = non assigné, jamais vide ; indexé |
| `created_at`, `updated_at` | timestamptz | `updated_at` mis à jour par l'ORM |
| `closed_at` | timestamptz | renseigné **si et seulement si** `statut = 'cloture'` ; `closed_at ≥ created_at` ; remis à NULL à la réouverture |
| `numero_reference` | int | **UNIQUE**, ≥ 1 ; référence affichée `INC-000001` (0003) |
| `titre`, `categorie` | varchar(255) | non vides ; `categorie` indexée (0003) |
| `playbook_id` | UUID FK → `playbooks` | `SET NULL` à la suppression du playbook ; indexé (0003) |
| `traite_le` | timestamptz | renseigné **si et seulement si** statut résolu ou clôturé ; `≥ created_at` (0003) |
| `escalade_le` | timestamptz | date de l'escalade automatique ; NULL = jamais escaladé (0003) |

Migration 0003 sur des incidents existants : numérotés par date de création, titre `Alerte <type du log>`, catégorie
= type du log, `traite_le` = date de clôture (sinon dernière mise à jour) pour les incidents résolus/clôturés.

## `etapes_realisees_incident` (feature `incidents`, 0003)

`incident_id` FK CASCADE, `etape_playbook_id` FK CASCADE, `UNIQUE(incident_id, etape_playbook_id)`, `realisee_le`,
`realisee_par` (NULL ou non vide). Absence de ligne = étape non réalisée.

## `playbooks` / `etapes_playbook` (feature `playbooks`, 0003)

`playbooks` : `nom` UNIQUE non vide, `description`, `categorie` UNIQUE (NULL permis, non vide sinon), `source`
**obligatoire** non vide, `created_at`, `updated_at`. `etapes_playbook` : `playbook_id` FK CASCADE, `ordre` ≥ 1,
`UNIQUE(playbook_id, ordre)`, `titre` non vide, `description`.

## `delais_reponse_incidents` (feature `incident_response_settings`, 0003)

`criticite` UNIQUE (CHECK niveaux), `delai_traitement_minutes` > 0, `escalade_automatique_activee`, `escalader_vers`
(NULL ou non vide), `updated_at`. 5 lignes insérées par la migration (valeurs par défaut à ajuster).

## `journal_audit` (feature `audit_journal`, 0003)

`date_evenement` (indexée), `type_evenement` (CHECK, indexé), `acteur`, `type_ressource`, `identifiant_ressource`,
`description` non vide, `details` JSONB, `adresse_ip`. Ajout seul.

Niveaux de criticité : `information`, `faible`, `moyenne`, `haute`, `critique` (provisoires).

## Pourquoi `batch_alter_table` dans les migrations

SQLite (tests) ne sait pas ajouter une contrainte à une table existante : Alembic recrée la table. Sur PostgreSQL, ce
sont de simples `ALTER TABLE`. `db/migrations/env.py` active `render_as_batch` pour les migrations autogénérées.

## Modifier le schéma

1. Modifier le modèle. 2. `alembic revision --autogenerate -m "description"`. 3. Relire la migration (types PostgreSQL, défauts). 4. Ajouter/adapter les tests dans `tests/test_database_schema.py` (et `tests/postgresql_integration/` si pertinent). 5. Mettre à jour ce document.
