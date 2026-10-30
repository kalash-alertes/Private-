# Outils du projet — rôle, niveau d'utilisation, intégration

Référence technique de tous les outils utilisés (ou prévus) par Intelligentsia SOC. Pour une vue simple, voir
[docs/overview/tools.md](../overview/tools.md). Les versions indiquées sont celles de `requirements.txt` et des fichiers
Docker ; voir la section « Versions » en fin de page pour l'écart avec l'environnement de développement local.

## Vue d'ensemble par couche

| Couche | Outil | Rôle | Statut |
|---|---|---|---|
| Source de données | FortiAnalyzer | Système d'origine des alertes | **Intégré** (API JSON-RPC ; première connexion réelle à valider) |
| Collecte | `backend/features/log_collection` + `backend/integrations/fortianalyzer` (httpx) | Lire l'API FortiAnalyzer (ou la démonstration), normaliser, dédoublonner | **En place** ([log_collection.md](./log_collection.md)) |
| Transformation | Data Prepper | Pipeline de transformation optionnel | **Optionnel, non décidé** |
| Recherche / stockage des logs | OpenSearch | Indexation et recherche des logs | **Prévu** |
| Interface analystes | Jinja2 (gabarits), python-multipart (formulaires), tzdata (fuseaux) | Pages HTML rendues en Python (`web_interface/`) | En place |
| API | Python, FastAPI, Uvicorn | Exposer les routes HTTP | En place |
| Validation | Pydantic, pydantic-settings | Valider entrées/sorties et configuration | En place |
| Accès aux données | SQLAlchemy, psycopg | ORM et pilote PostgreSQL | En place |
| Schéma de base | Alembic | Migrations versionnées | En place |
| Base de données | PostgreSQL 16 | Données métier (imports, logs, incidents) | En place |
| Exécution | Docker, Docker Compose (dans WSL sur ce poste) | Lancer base + backend en local | En place (backend en conteneur non revérifié) |
| Tests | pytest, httpx (TestClient), SQLite | Tests unitaires, routes, intégration PostgreSQL | En place |
| Code source | Git, GitHub | Versionnement, branches | En place |
| Assistants IA | `AGENTS.md`, `.github/copilot-instructions.md` | Règles de code pour les IA | En place |

Flux cible : FortiAnalyzer → collecteur → OpenSearch (logs) et PostgreSQL (métadonnées, incidents, imports) → API
FastAPI → interface web (`web_interface/`, à la racine) et API JSON (`/api`).

---

## Application (backend)

### Python
- **Rôle** : langage de tout le backend, des migrations et des tests.
- **Niveau** : partout (`backend/`, `db/migrations/`, `tests/`).
- **Intégration** : image Docker `python:3.12-slim` (`Dockerfile`). En local : `pip install -r requirements.txt`.

### FastAPI (`fastapi==0.115.0`)
- **Rôle** : framework HTTP. Déclare les routes, injecte les dépendances (session DB, pagination), génère `/docs`.
- **Niveau** : `backend/main.py` (création de l'application, CORS, `/health`) et `backend/features/<feature>/router.py`.
  Un router n'a **aucune logique métier** : il appelle le `service.py` de sa feature.
- **Intégration** :
  1. créer un `APIRouter` dans `router.py` de la feature ;
  2. l'inclure dans `backend/main.py` (`application.include_router(...)`) ;
  3. les erreurs métier (`backend/core/domain_errors.py`) sont traduites en 404/409/422 par
     `backend/core/http_error_handlers.py`, enregistré dans `main.py`.

### Uvicorn (`uvicorn[standard]==0.30.6`)
- **Rôle** : serveur ASGI qui exécute l'application FastAPI.
- **Niveau** : démarrage uniquement (`CMD` du `Dockerfile`, `command` du service `backend` dans `docker-compose.yml`).
- **Intégration** : `uvicorn backend.main:application --host 0.0.0.0 --port 8000` (`--reload` en développement).

### Jinja2 (`jinja2==3.1.4`), python-multipart (`python-multipart==0.0.12`), tzdata (`tzdata==2024.2`)
- **Rôle** : rendu des pages HTML de l'interface (Jinja2, échappement automatique) ; lecture des formulaires HTML par
  FastAPI (python-multipart) ; base des fuseaux horaires pour afficher les dates en `Europe/Paris` (tzdata, absente de
  certaines images Docker « slim » et de Windows).
- **Niveau** : `web_interface/` uniquement. Le backend métier n'en dépend pas.
- **Intégration** : `web_interface/template_rendering.py` (moteur, filtres) ; `web_interface_registration.py`
  (branchement dans `backend/main.py`). Voir [web_interface.md](./web_interface.md).
- **Remplace** : OpenSearch Dashboards et le frontend React de la maquette comme interface des analystes (décision du
  2026-10-29). Le dossier `frontend/` (squelette sans rapport) n'est pas utilisé.

### Pydantic (`pydantic==2.9.2`)
- **Rôle** : valider toute donnée externe (corps HTTP, filtres, futur contenu FortiAnalyzer) et formater les réponses.
- **Niveau** : `backend/features/<feature>/schemas.py` et `backend/core/` (`pagination.py`, `utc_datetime_types.py`).
- **Conventions** : `extra="forbid"` sur les entrées (champ inconnu ⇒ 422) ; dates sans fuseau refusées puis converties
  en UTC (`AwareUtcDatetimeInput`) ; règles croisées dans des `model_validator` (ex. justification obligatoire d'un
  faux positif).
- **Intégration** : déclarer un schéma dans `schemas.py`, l'utiliser comme type de paramètre de route ou d'entrée de
  service. Ne jamais passer un `dict` brut d'une source externe au service.

### pydantic-settings (`pydantic-settings==2.6.0`)
- **Rôle** : lire la configuration depuis les variables d'environnement et le fichier `.env`.
- **Niveau** : `backend/core/settings.py` uniquement (`get_application_settings()`, mise en cache).
- **Intégration** : ajouter un champ à `ApplicationSettings`, puis la variable correspondante (sans valeur réelle) dans
  `.env.example`. **Aucun secret dans le code** ; `.env` n'est jamais commité (`.gitignore`).

### SQLAlchemy (`sqlalchemy==2.0.35`)
- **Rôle** : ORM et constructeur de requêtes SQL.
- **Niveau** :
  - `backend/core/database.py` : moteur, fabrique de sessions, dépendance `get_database_session` ;
  - `backend/features/<feature>/models.py` : tables (contraintes CHECK/UNIQUE/FK déclarées ici **et** en migration) ;
  - `backend/features/<feature>/repository.py` : **seul endroit où l'on écrit des requêtes** ;
  - `backend/database_model_registry.py` : importe tous les modèles (Alembic et tests en ont besoin).
- **Techniques utilisées** : `INSERT ... ON CONFLICT DO NOTHING` (logs idempotents), `SELECT ... FOR UPDATE`
  (modifications concurrentes), SAVEPOINT (`begin_nested`, création d'incident), `func.now()` (horloge de la base).
- **Intégration** : nouveau modèle ⇒ l'importer dans `database_model_registry.py`, puis générer une migration Alembic.

### psycopg (`psycopg[binary]==3.2.3`)
- **Rôle** : pilote PostgreSQL utilisé par SQLAlchemy.
- **Niveau** : invisible dans le code ; sélectionné par le préfixe d'URL `postgresql+psycopg://` de `DATABASE_URL`.

---

## Base de données

### PostgreSQL 16 (`postgres:16-alpine`)
- **Rôle** : **seule** base de l'application : exécutions d'import, métadonnées des logs, incidents.
- **Niveau** : service `database` de `docker-compose.yml` ; port lié à `127.0.0.1` uniquement ; données dans le volume
  `postgres_data`.
- **Règles** (AGENTS.md §5) : `TIMESTAMPTZ` en UTC, clés UUID, contraintes en base, criticité source jamais écrasée.
  Schéma décrit dans [database.md](./database.md).
- **Intégration** : variables `POSTGRES_*` dans `.env` ; le backend s'y connecte via `DATABASE_URL`.

### Alembic (`alembic==1.13.3`)
- **Rôle** : migrations de schéma versionnées. **Toute** modification de schéma passe par Alembic.
- **Niveau** : `alembic.ini` (racine), `db/migrations/env.py` (lit `DATABASE_URL` via `backend.core.settings`),
  `db/migrations/versions/` (`0001` schéma initial, `0002` contraintes de cohérence).
- **Commandes** :
  ```powershell
  alembic upgrade head                                   # appliquer
  alembic revision --autogenerate -m "description"       # générer, puis relire et corriger à la main
  alembic downgrade -1                                    # revenir d'une version (développement uniquement)
  ```
- **Intégration** : le conteneur backend exécute `alembic upgrade head` avant de démarrer. `render_as_batch=True`
  permet aux mêmes migrations de tourner sur SQLite (tests).

### SQLite (bibliothèque standard Python)
- **Rôle** : **uniquement** base temporaire des tests rapides de logique. Jamais utilisée par l'application.
- **Niveau** : `tests/conftest.py` (base créée en appliquant les vraies migrations Alembic).
- **Limite** : ne valide pas le comportement PostgreSQL (verrous, concurrence, fuseaux). Voir [testing.md](./testing.md).

---

## Exécution locale

### Docker et Docker Compose
- **Rôle** : lancer PostgreSQL et le backend dans des conteneurs reproductibles.
- **Niveau** : `Dockerfile` (image backend, utilisateur non-root `backend_runner`), `.dockerignore` (exclut `.env`,
  `tests`, `docs`...), `docker-compose.yml` (services `database` et `backend`).
- **Commandes** :
  ```powershell
  Copy-Item .env.example .env          # puis adapter les valeurs
  docker compose up --build            # base + backend
  docker compose up -d database        # base seule (pour les tests PostgreSQL)
  ```
- **Sur ce poste, Docker est installé dans WSL** : préfixer par `wsl --cd /mnt/f/shared_folder/Intelligentsia_SOC`.
  WSL arrête sa machine virtuelle (et les conteneurs) dès qu'aucune commande `wsl` n'est active : garder un terminal
  ouvert avec `docker compose up database`.
- **Statut** : base validée en conteneur ; lancement du conteneur `backend` par `docker compose up --build`
  **non revérifié** après les derniers ajouts.

---

## Tests

### httpx en production : client FortiAnalyzer
- **Rôle** : en plus des tests, httpx est le client HTTP du connecteur FortiAnalyzer
  (`backend/integrations/fortianalyzer/fortianalyzer_json_rpc_client.py`) : HTTPS, vérification TLS (booléen ou
  fichier CA), délai maximal. En test, `httpx.MockTransport` remplace le réseau par un faux FortiAnalyzer.

### pytest et httpx (versions : voir `requirements.txt`)
- **Rôle** : pytest exécute les tests ; httpx est requis par le `TestClient` de FastAPI pour tester les routes sans
  serveur réel.
- **Niveau** : `pytest.ini` (marqueur `postgresql`), `tests/` (miroir de `backend/`), `tests/conftest.py` (fixtures),
  `tests/synthetic_data.py` (données **inventées**, préfixe `SYNTHETIQUE-`), `tests/postgresql_integration/`.
- **Commandes** :
  ```powershell
  python -m pytest -rs
  $env:TEST_POSTGRESQL_DATABASE_URL = "postgresql+psycopg://soc:change_me_locally@localhost:5432/soc_incidents_test"
  python -m pytest tests/postgresql_integration -rs
  ```
- **Intégration** : chaque nouvelle feature ajoute ses tests dans `tests/features/<feature>/`. Les intégrations externes
  (FortiAnalyzer, OpenSearch) seront testées avec des **faux**, jamais avec de vrais appels réseau.

---

## Outils prévus (non intégrés)

Ces outils sont décrits dans [explain_project.md](../../explain_project.md). **Aucun n'est encore branché** et ils
n'ont pas été ajoutés à `docker-compose.yml` : ils le seront avec la fonctionnalité qui en a besoin.

| Outil | Rôle prévu | Où il s'intégrera | Prérequis |
|---|---|---|---|
| OpenSearch | Stockage indexé et recherche des logs | `backend/integrations/opensearch/` ; service ajouté au compose ; `logs.reference_opensearch` relie les deux bases | Décision sur l'emplacement du log brut (PostgreSQL, OpenSearch ou les deux) |
| Data Prepper | Transformation / pipelines entre collecteur et OpenSearch | Service du compose, si les volumes ou transformations le justifient | Décision d'architecture |

---

## Ajouter un nouvel outil : procédure

1. Vérifier qu'il répond à un besoin du cadrage (`explain_project.md`) ; ne pas l'ajouter « en avance ».
2. Dépendance Python ⇒ version épinglée dans `requirements.txt`. Service ⇒ entrée dans `docker-compose.yml`, ports liés
   à `127.0.0.1`.
3. Service externe ⇒ client isolé dans `backend/integrations/<nom>/`, derrière une interface, avec un faux pour les tests.
4. Configuration ⇒ champ dans `backend/core/settings.py` et variable sans secret dans `.env.example`.
5. Mettre à jour cette page **et** [docs/overview/tools.md](../overview/tools.md).

## Versions

`requirements.txt` épingle les versions de l'image Docker (Python 3.12). Le code a été testé localement avec des
versions plus récentes (Python 3.14, SQLAlchemy 2.1, FastAPI 0.141, Pydantic 2.13, Alembic 1.20, psycopg 3.2.13).
L'exécution avec les versions épinglées n'a pas encore été vérifiée.

## Sécurité

L'application n'a ni authentification, ni autorisations, ni durcissement : **elle n'est pas prête pour la production**
et ne doit pas être exposée hors d'un poste de développement.
