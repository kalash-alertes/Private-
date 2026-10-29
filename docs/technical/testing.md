# Tests

## Lancer

```powershell
python -m pytest            # tests SQLite ; les tests PostgreSQL sont ignorés (« skipped ») sans base de test
python -m pytest -rs        # affiche la raison des tests ignorés
```

## Deux niveaux

| Niveau | Dossier | Base | Ce qui est validé |
|---|---|---|---|
| Unitaires / fonctionnels | `tests/` (hors `postgresql_integration`) | SQLite temporaire, **vraies migrations Alembic** | règles métier, routes, contraintes CHECK/UNIQUE/FK, idempotence séquentielle |
| Intégration PostgreSQL | `tests/postgresql_integration/` | PostgreSQL réel | types natifs (UUID, JSONB, TIMESTAMPTZ), migrations aller-retour, contraintes, **concurrence** (verrous, ON CONFLICT, UNIQUE) |

Un test SQLite réussi **n'est pas** une validation PostgreSQL : SQLite ignore `SELECT ... FOR UPDATE`, sérialise toutes
les écritures et ne conserve pas les fuseaux horaires.

## Activer les tests PostgreSQL

La base est **vidée** par les tests : utiliser une base dédiée dont le nom contient `test` (garde-fou dans `conftest.py`).

```powershell
docker compose up -d database
docker compose exec database createdb -U soc soc_incidents_test
$env:TEST_POSTGRESQL_DATABASE_URL = "postgresql+psycopg://soc:change_me_locally@localhost:5432/soc_incidents_test"
python -m pytest tests/postgresql_integration -rs
```

(Adapter utilisateur / mot de passe aux valeurs de votre `.env`.)

**Docker installé dans WSL** : préfixer les commandes Docker par `wsl --cd /mnt/f/shared_folder/Intelligentsia_SOC`.
WSL arrête sa machine virtuelle (et donc Docker et PostgreSQL) dès qu'aucune commande `wsl` n'est active : garder une
session ouverte, par exemple en lançant la base au premier plan dans un terminal dédié
(`wsl --cd /mnt/f/shared_folder/Intelligentsia_SOC docker compose up database`). Le port 5432 est joignable depuis
Windows via `127.0.0.1`.

## Dernière validation PostgreSQL

2026-10-28 : PostgreSQL 16 (image `postgres:16-alpine`, Docker dans WSL) — 7/7 tests d'intégration réussis, 5 exécutions
consécutives ; migrations `0001` → `0002` appliquées sur la base principale ; parcours API complet (création d'incident,
doublon 409, réévaluation, clôture, réouverture) vérifié sur PostgreSQL avec des données synthétiques ensuite supprimées.

## Données synthétiques

`tests/synthetic_data.py` fabrique des logs **inventés** (identifiants préfixés `SYNTHETIQUE-`). Ils ne reflètent pas le
format FortiAnalyzer et ne prouvent pas qu'une collecte réelle fonctionne.

## Détails techniques

- `tests/conftest.py` corrige la gestion des transactions du pilote `sqlite3` (recette SQLAlchemy) pour que les SAVEPOINT
  fonctionnent comme sur PostgreSQL, et active les clés étrangères.
- Le client HTTP de test remplace la dépendance `get_database_session` par une session sur la base de test.
