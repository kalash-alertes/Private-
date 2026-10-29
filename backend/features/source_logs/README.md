# Feature `source_logs`

**Rôle** : logs critiques connus de l'application (table `logs`), déduplication via `identifiant_source`.
Aucune route d'ingestion : l'enregistrement passe par `service.store_source_log_if_new` (collecteur).

**Fichiers** : `models.py` · `schemas.py` (`NewSourceLogData`, `SourceLogMetadataRead`, `SourceLogDetailRead`, filtres) ·
`repository.py` (`INSERT ... ON CONFLICT DO NOTHING`) · `service.py` · `router.py` (`GET /logs[/{id}]`).

**Tester** : `python -m pytest tests/features/source_logs`.

**Doc** : [docs/technical/source_logs.md](../../../docs/technical/source_logs.md). Suivre [AGENTS.md](../../../AGENTS.md).
**Attention** : ne jamais modifier `criticite_source` d'un log existant.
