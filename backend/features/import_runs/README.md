# Feature `import_runs`

**Rôle** : historique des collectes FortiAnalyzer (table `executions_import`). Démarrer/terminer une exécution est réservé
au code interne (futur collecteur) ; l'API HTTP ne fait que consulter.

**Fichiers** : `models.py` (table + CHECK) · `schemas.py` (`ImportRunRead`, `ImportRunFinishedOutcome`) ·
`repository.py` · `service.py` (`start_import_run`, `finish_import_run`, `ensure_import_run_accepts_new_logs`, consultation) ·
`error_message_sanitizer.py` (masquage des secrets dans `erreur`) · `router.py` (`GET /executions-import[/{id}]`).

**Tester** : `python -m pytest tests/features/import_runs`.

**Doc** : [docs/technical/import_runs.md](../../../docs/technical/import_runs.md). Suivre [AGENTS.md](../../../AGENTS.md).
