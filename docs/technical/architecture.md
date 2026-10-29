# Architecture technique du backend

## Stack

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Pydantic v2. Déploiement dev : Docker Compose (`database` + `backend`).
OpenSearch, Dashboards et Data Prepper seront ajoutés au compose quand la fonctionnalité de collecte/indexation sera codée.

## Organisation du code

```
backend/
  main.py                    Création de l'application FastAPI, /health, CORS
  database_model_registry.py Importe tous les modèles (pour Alembic et les tests)
  core/                      settings.py (config .env), database.py (SQLAlchemy), criticality.py (niveaux communs),
                             domain_errors.py + http_error_handlers.py (erreurs métier -> 404/409/422),
                             pagination.py (limit/offset), utc_datetime_types.py (dates UTC en entrée/sortie)
  features/<feature>/        models.py, schemas.py, repository.py, service.py, router.py, README.md
  integrations/<systeme>/    Clients externes derrière une interface (FortiAnalyzer, OpenSearch)
db/migrations/               Alembic : env.py lit DATABASE_URL via backend.core.settings
tests/                       pytest : SQLite + vraies migrations ; tests/postgresql_integration/ (PostgreSQL réel)
```

## Règles d'architecture

- Chaîne d'appel : `router` → `service` → `repository` → DB. Aucun saut de couche.
- Une feature n'importe pas le code interne d'une autre ; elle passe par un `service.py` public ou une clé étrangère.
- `core/` ne dépend d'aucune feature. Seul `database_model_registry.py` connaît toutes les tables.
- Ajouter une fonctionnalité : créer `backend/features/<nom>/`, importer ses modèles dans `database_model_registry.py`,
  générer la migration (`alembic revision --autogenerate -m "..."`, puis relire/corriger), brancher le router dans `main.py`,
  écrire tests + docs technique et humaine.

## Fonctionnalités et dépendances

| Feature | Routes | Doc | Dépend de (service public) |
|---|---|---|---|
| `import_runs` | `GET /executions-import`, `GET /executions-import/{id}` | [import_runs.md](./import_runs.md) | — |
| `source_logs` | `GET /logs`, `GET /logs/{id}` | [source_logs.md](./source_logs.md) | `import_runs` |
| `incidents` | `POST/GET /incidents`, `GET /incidents/{id}`, `PUT /incidents/{id}/{statut,criticite-actuelle,faux-positif,assignation}` | [incidents.md](./incidents.md) | `source_logs` |

Conventions transverses :
- **Transactions** : chaque fonction de service qui écrit fait son propre `commit` (une action = une transaction).
  La session HTTP est fermée en fin de requête (rollback de ce qui n'a pas été validé).
- **Erreurs** : les services lèvent `ResourceNotFoundError` (404), `ResourceConflictError` (409),
  `BusinessRuleViolationError` (422) ; réponse `{"detail", "error_code"}`.
- **Pagination** : `limit` (1–200, défaut 50) et `offset` ; réponse `{items, total, limit, offset}` ; tri déterministe
  (date desc puis id desc).
- **Dates** : refus des dates entrantes sans fuseau, conversion en UTC ; les dates sortantes portent toujours un fuseau.
- **Pas d'authentification** pour l'instant : l'API ne doit pas être exposée hors d'un poste de développement.

## Flux cible (cf. explain_project.md)

FortiAnalyzer → collecteur (`integrations/fortianalyzer` + feature d'import) → OpenSearch (logs) et PostgreSQL (métadonnées, incidents, imports) → API → frontend analyste.

## Décisions et points ouverts

- **Statuts d'incident** et **niveaux de criticité** : valeurs provisoires (voir `backend/core/criticality.py`, `incidents/models.py`). À confirmer avec les niveaux réels de FortiAnalyzer ; tout changement = migration.
- **Utilisateurs / authentification** non décidés : `incidents.assigne_a` est du texte libre pour l'instant.
- **Clé de déduplication** : `logs.identifiant_source` est obligatoire et unique ; le collecteur devra le calculer de façon déterministe si FortiAnalyzer n'en fournit pas.
- **Base de données** : PostgreSQL est la seule base de l'application. SQLite ne sert qu'aux tests rapides de logique.
- **Tests** : tests PostgreSQL (`tests/postgresql_integration/`) exécutés si `TEST_POSTGRESQL_DATABASE_URL` est défini ;
  validés le 2026-10-28 sur PostgreSQL 16 ; à brancher en CI. Voir [testing.md](./testing.md).
- **Versions** : `requirements.txt` épingle les versions de l'image Docker (Python 3.12). Le code a été testé localement
  avec des versions plus récentes (Python 3.14, SQLAlchemy 2.1, FastAPI 0.141, Pydantic 2.13) ; il évite les API
  propres à ces versions, mais l'exécution avec les versions épinglées n'a pas encore été vérifiée.
