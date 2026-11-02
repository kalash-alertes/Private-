# Feature `incidents`

**Rôle** : suivi métier d'un incident — référence `INC-000001`, titre, catégorie, statut (ouvert / traité), criticité
réévaluée, faux positif, responsable, playbook suivi et avancement de ses étapes, checklist de réponse, délai de
traitement, escalade. Tables `incidents`, `etapes_realisees_incident` et `incident_response_checklist`.

**Fichiers**
- `models.py` · `schemas.py` (une requête par action ; vues liste/détail/playbook) · `repository.py`
- `service.py` : cycle de vie (création, statut, criticité, titre, catégorie, faux positif, attribution, playbook)
- `incident_views.py` : valeurs calculées (date limite, délai dépassé, plan, alertes) pour la liste et le détail
- `incident_playbook_progress.py` : playbook de l'incident et étapes cochées
- `incident_response_checklist.py` : checklist générique par incident, progression et audit
- `automatic_escalation.py` : escalade des incidents en retard (+ boucle périodique optionnelle)
- `incident_statistics.py` : indicateurs pour le tableau de bord
- `incident_audit_trail.py` : écriture dans le journal d'audit
- `router.py` : routes `/api/incidents/...`

**Tester** : `python -m pytest tests/features/incidents`.

Chaque nouvel incident reçoit sept tâches d'aide-mémoire, indépendantes du playbook et cochables séparément. La migration
0004 ajoute la table et initialise aussi les incidents déjà présents. Les tâches terminées sont datées, attribuables
facultativement et écrites dans le journal d'audit ; les incidents clôturés restent en lecture seule.

**Doc** : [docs/technical/incidents.md](../../../docs/technical/incidents.md). Suivre [AGENTS.md](../../../AGENTS.md).
**Attention** : ne jamais modifier `logs.criticite_source` ; la réévaluation se fait dans `criticite_actuelle`.
