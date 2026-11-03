# Feature `raw_syslog_feed`

**Rôle** : montrer les logs syslog tels qu'envoyés par FortiAnalyzer, en direct et AVANT le filtre de sévérité, avec
ce que la collecte en fera (enregistré / écarté) et la répartition par niveau. Explique l'écart entre la vue de
FortiAnalyzer et la base. Aucune table : lit la mémoire bornée du récepteur syslog.

**Fichiers**
- `service.py` : `read_raw_syslog_feed` (filtres, devenir de chaque log, bilan par niveau, pertes)
- `schemas.py` · `router.py` (`GET /api/logs-bruts`)
- Page : `web_interface/pages/raw_syslog_feed_page.py` (`/logs-bruts`, fragment `/logs-bruts/nouveaux`)

**Dépend de** : `log_collection` (service public `evaluate_raw_log_against_collection_threshold`),
`backend/integrations/fortianalyzer` (mémoire d'affichage, compteurs).

**Tester** : `python -m pytest tests/features/raw_syslog_feed tests/integrations`.

**Doc** : [docs/technical/raw_syslog_feed.md](../../../docs/technical/raw_syslog_feed.md).
