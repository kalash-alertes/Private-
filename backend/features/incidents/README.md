# Feature `incidents`

**Rôle** : suivi métier d'un incident (statut, criticité réévaluée, faux positif, attribution, clôture/réouverture) — table `incidents`.

**Fichiers** : `models.py` · `schemas.py` (une requête par action) · `repository.py` (SAVEPOINT à la création,
`FOR UPDATE` aux modifications) · `service.py` (règles, dont les règles PROVISOIRES listées en tête) · `router.py`.

**Tester** : `python -m pytest tests/features/incidents`.

**Doc** : [docs/technical/incidents.md](../../../docs/technical/incidents.md). Suivre [AGENTS.md](../../../AGENTS.md).
**Attention** : ne jamais modifier `logs.criticite_source` ; la réévaluation se fait dans `criticite_actuelle`.
