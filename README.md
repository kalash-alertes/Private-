# Intelligentsia SOC

Application de gestion des alertes et incidents issus de FortiAnalyzer. Cadrage complet : [explain_project.md](./explain_project.md).

## Pour les IA et développeurs

Lire [AGENTS.md](./AGENTS.md) avant tout changement (nommage, modularité, commentaires, docs, tests).

## Démarrer (Docker)

```powershell
Copy-Item .env.example .env      # puis adapter les valeurs
docker compose up --build
```

- API : http://localhost:8000 (santé : `/health`, documentation interactive : `/docs`)
- PostgreSQL : `localhost:5432` (accessible uniquement depuis la machine locale)
- Les migrations sont appliquées automatiquement au démarrage du backend.

## Tests (sans Docker)

```powershell
pip install -r requirements.txt
python -m pytest
```

Les tests PostgreSQL (`tests/postgresql_integration/`) sont ignorés tant que `TEST_POSTGRESQL_DATABASE_URL` n'est pas
défini : voir [docs/technical/testing.md](./docs/technical/testing.md).

## API disponible (sans authentification : usage local uniquement)

`/executions-import` (historique des imports), `/logs` (consultation des logs), `/incidents` (création et suivi).
Détail interactif : `/docs`. **Pas prêt pour la production** (ni authentification, ni autorisations, ni durcissement).

## Organisation

| Dossier | Contenu |
|---|---|
| `backend/core/` | Configuration, connexion DB, valeurs communes |
| `backend/features/` | Une fonctionnalité = un module indépendant (`import_runs`, `source_logs`, `incidents`) |
| `backend/integrations/` | Adaptateurs vers FortiAnalyzer, OpenSearch... |
| `db/migrations/` | Migrations Alembic (schéma PostgreSQL) |
| `docs/technical/` | Documentation détaillée (développeurs / IA) |
| `docs/overview/` | Documentation de vue d'ensemble (humains) |
| `frontend/` | Interface analyste (à venir) |

## Documentation

- Vue d'ensemble : [docs/overview/project_overview.md](./docs/overview/project_overview.md)
- Outils (rôle, niveau d'utilisation, intégration) : [vue simple](./docs/overview/tools.md) · [détail technique](./docs/technical/tools.md)
- Architecture technique : [docs/technical/architecture.md](./docs/technical/architecture.md)
- Base de données : [docs/technical/database.md](./docs/technical/database.md)
- Fonctionnalités : [imports](./docs/technical/import_runs.md) · [logs](./docs/technical/source_logs.md) · [incidents](./docs/technical/incidents.md) · [tests](./docs/technical/testing.md)
- Parcours d'un incident (vue simple) : [docs/overview/incident_workflow.md](./docs/overview/incident_workflow.md)
