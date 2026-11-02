# Intelligentsia SOC

Application de gestion des alertes et incidents issus de FortiAnalyzer. Cadrage complet : [explain_project.md](./explain_project.md).

## Pour les IA et développeurs

Lire [AGENTS.md](./AGENTS.md) avant tout changement (nommage, modularité, commentaires, docs, tests).

## Démarrer (Docker)

Guide complet (première fois, tous les jours, données de test, dépannage) :
**[docs/overview/running_the_application.md](./docs/overview/running_the_application.md)**.
Brancher le vrai FortiAnalyzer (`APP_IS_IN_DEMO=false`) : **[docs/overview/connecting_fortianalyzer.md](./docs/overview/connecting_fortianalyzer.md)**.

```powershell
Copy-Item .env.example .env                           # une seule fois, puis adapter les valeurs
powershell -File scripts\download_docker_wheels.ps1   # une fois, et après chaque changement de requirements.txt
wsl docker compose up --build -d                      # sur ce poste, Docker tourne dans WSL
```

Le script télécharge les paquets Python depuis Windows dans `docker_wheels/` : l'image est ensuite construite sans
accès Internet, car depuis Docker sous WSL les téléchargements PyPI se coupent. Voir `docker_wheels/README.md`.
Arrêter : `wsl docker compose down` (les données de la base sont conservées).

- **Interface analystes** : http://localhost:8000
- API JSON : http://localhost:8000/api (santé : `/api/health`, documentation interactive : `/docs`)
- PostgreSQL : `localhost:5432` (accessible uniquement depuis la machine locale)
- Les migrations sont appliquées automatiquement au démarrage du backend.
- Données de démonstration (inventées) pour voir les écrans remplis :
  `wsl docker compose exec backend python -m scripts.load_synthetic_demo_data`

## Tests (sans Docker)

```powershell
pip install -r requirements.txt
python -m pytest
```

Les tests PostgreSQL (`tests/postgresql_integration/`) sont ignorés tant que `TEST_POSTGRESQL_DATABASE_URL` n'est pas
défini : voir [docs/technical/testing.md](./docs/technical/testing.md).

## API disponible (sans authentification : usage local uniquement)

Sous `/api` : `/executions-import` (imports), `/logs` (alertes), `/incidents` (création, suivi, playbook, escalade),
`/parametres/playbooks`, `/parametres/reponse-incidents/delais`, `/parametres/journal-audit`, `/tableau-de-bord`,
`/collecte` (collecte des alertes).
Détail interactif : `/docs`. **Pas prêt pour la production** (ni authentification, ni autorisations, ni durcissement).

## Organisation

| Dossier | Contenu |
|---|---|
| `backend/core/` | Configuration, connexion DB, valeurs communes |
| `backend/features/` | Une fonctionnalité = un module indépendant (`import_runs`, `source_logs`, `incidents`, `playbooks`, `incident_response_settings`, `audit_journal`, `dashboard`, `log_collection`) |
| `web_interface/` | Interface analystes en Python : une page = un fichier `pages/*.py` + un gabarit `templates/pages/*.html` ; CSS dans `static/css/` |
| `scripts/` | Outils de développement (données de démonstration synthétiques) |
| `backend/integrations/` | Adaptateurs externes : `fortianalyzer/` (client réel + démonstration) |
| `db/migrations/` | Migrations Alembic (schéma PostgreSQL) |
| `docs/technical/` | Documentation détaillée (développeurs / IA) |
| `docs/overview/` | Documentation de vue d'ensemble (humains) |
| `frontend/` | Squelette non utilisé (l'interface est `web_interface/`) |

## Documentation

- **Comprendre le code pas à pas** : [docs/guide_lecture_code/](./docs/guide_lecture_code/README.md)

- Vue d'ensemble : [docs/overview/project_overview.md](./docs/overview/project_overview.md)
- Outils (rôle, niveau d'utilisation, intégration) : [vue simple](./docs/overview/tools.md) · [détail technique](./docs/technical/tools.md)
- Architecture technique : [docs/technical/architecture.md](./docs/technical/architecture.md)
- Base de données : [docs/technical/database.md](./docs/technical/database.md)
- Fonctionnalités : [imports](./docs/technical/import_runs.md) · [logs](./docs/technical/source_logs.md) · [incidents](./docs/technical/incidents.md) · [playbooks](./docs/technical/playbooks.md) · [délais et escalade](./docs/technical/incident_response_settings.md) · [journal d'audit](./docs/technical/audit_journal.md) · [tableau de bord](./docs/technical/dashboard.md) · [collecte FortiAnalyzer](./docs/technical/log_collection.md) · [tests](./docs/technical/testing.md)
- Interface web : [technique](./docs/technical/web_interface.md) · [vue simple](./docs/overview/interface.md)
- Parcours d'un incident (vue simple) : [docs/overview/incident_workflow.md](./docs/overview/incident_workflow.md)
- Paramètres, playbooks, délais, audit (vue simple) : [docs/overview/settings_and_playbooks.md](./docs/overview/settings_and_playbooks.md)
