# Architecture technique du backend

## Stack

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Pydantic v2, Jinja2 (interface). Déploiement dev : Docker
Compose (`database` + `backend`). Le backend sert à la fois l'**interface web** (racine `/`) et l'**API JSON** (`/api`).
OpenSearch et Data Prepper (optionnel) seront ajoutés avec la collecte. **OpenSearch Dashboards n'est plus l'interface
prévue** : décision du 2026-10-29, l'interface est `web_interface/` (voir [web_interface.md](./web_interface.md)).

## Organisation du code

```
backend/
  main.py                    Création de l'application FastAPI, /health, CORS
  database_model_registry.py Importe tous les modèles (pour Alembic et les tests)
  core/                      settings.py (config .env), database.py (SQLAlchemy), criticality.py (niveaux communs),
                             domain_errors.py + http_error_handlers.py (erreurs métier -> 404/409/422),
                             pagination.py (limit/offset), utc_datetime_types.py (dates UTC en entrée/sortie)
  features/<feature>/        models.py, schemas.py, repository.py, service.py, router.py, README.md
  integrations/fortianalyzer/ Sources d'alertes : client JSON-RPC réel + démonstration (APP_IS_IN_DEMO)
web_interface/               Interface analystes en Python : pages/ (une par page), templates/, static/css/
scripts/                     Outils de développement (données de démonstration synthétiques)
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
| `import_runs` | `GET /api/executions-import`, `GET /api/executions-import/{id}` | [import_runs.md](./import_runs.md) | — |
| `source_logs` | `GET /api/logs`, `GET /api/logs/{id}` | [source_logs.md](./source_logs.md) | `import_runs` |
| `incidents` | `/api/incidents...` (cycle de vie, playbook, étapes, escalade) | [incidents.md](./incidents.md) | `source_logs`, `playbooks`, `incident_response_settings`, `audit_journal` |
| `playbooks` | `/api/parametres/playbooks...` | [playbooks.md](./playbooks.md) | `audit_journal` |
| `incident_response_settings` | `/api/parametres/reponse-incidents/delais...` | [incident_response_settings.md](./incident_response_settings.md) | `audit_journal` |
| `audit_journal` | `GET /api/parametres/journal-audit` | [audit_journal.md](./audit_journal.md) | — |
| `dashboard` | `GET /api/tableau-de-bord` | [dashboard.md](./dashboard.md) | `source_logs`, `incidents` |
| `log_collection` | `POST /api/collecte`, `GET /api/collecte/configuration` | [log_collection.md](./log_collection.md) | `import_runs`, `source_logs`, `integrations/fortianalyzer` |

Toutes les routes de l'API sont préfixées par `/api` (y compris `/api/health`). L'interface web (`web_interface/`)
n'a pas de logique métier : elle appelle les mêmes services publics.

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

FortiAnalyzer → collecteur (`integrations/fortianalyzer` + feature d'import) → OpenSearch (logs) et PostgreSQL (métadonnées, incidents, imports) → services → interface web (`/`) et API JSON (`/api`).

## Décisions et points ouverts

- **Statuts d'incident** et **niveaux de criticité** : valeurs provisoires (voir `backend/core/criticality.py`, `incidents/models.py`). À confirmer avec les niveaux réels de FortiAnalyzer ; tout changement = migration.
- **Utilisateurs / authentification** non décidés : `incidents.assigne_a` est du texte libre ; le journal d'audit ne
  connaît pas encore l'auteur des actions ; protection CSRF à ajouter avec l'authentification.
- **Paramètres Clients et Utilisateurs** : sections présentes dans l'interface, jugées non prioritaires (vides).
- **Clé de déduplication** : `logs.identifiant_source` est obligatoire et unique ; le collecteur devra le calculer de façon déterministe si FortiAnalyzer n'en fournit pas.
- **Base de données** : PostgreSQL est la seule base de l'application. SQLite ne sert qu'aux tests rapides de logique.
- **Tests** : tests PostgreSQL (`tests/postgresql_integration/`) exécutés si `TEST_POSTGRESQL_DATABASE_URL` est défini ;
  validés le 2026-10-28 sur PostgreSQL 16 ; à brancher en CI. Voir [testing.md](./testing.md).
- **Versions** : `requirements.txt` épingle des versions valables à la fois pour Python 3.12 (image Docker) et 3.14
  (poste Windows) ; vérifié le 2026-10-29 (tests sous Windows, application lancée dans Docker sur PostgreSQL 16,
  migration 0003 appliquée). Les anciennes versions (2024) n'existaient pas pour Python 3.14 ; `sqlalchemy==2.1.0`
  n'était pas installable pour 3.12, d'où 2.1.6.
- **Construction de l'image hors ligne** : `scripts/download_docker_wheels.ps1` remplit `docker_wheels/` depuis
  Windows ; le `Dockerfile` installe depuis ce dossier s'il est rempli, sinon depuis PyPI.
