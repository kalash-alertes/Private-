# Fonctionnalité `dashboard` — tableau de bord

Code : `backend/features/dashboard/` (aucune table). Route : `GET /api/tableau-de-bord?nombre_jours=7` (1–90).
Interface : `/`.

| Champ | Calcul |
|---|---|
| `nombre_incidents_ouverts` / `_traites` | statuts nouveau, en_cours, en_attente / résolu, clôturé |
| `nombre_incidents_ouverts_delai_depasse` | ouverts dont la date limite est passée (même calcul que la liste) |
| `nombre_alertes` / `nombre_alertes_a_traiter` | tous les logs / logs − incidents (un log = au plus un incident en V1) |
| `temps_moyen_traitement_minutes` | moyenne de `traite_le − created_at` sur les incidents traités ; null si aucun |
| `incidents_ouverts_par_criticite` | répartition des incidents ouverts par criticité actuelle |
| `activite[]` | par jour UTC : logs par `date_evenement`, incidents par `traite_le` (jours sans activité = 0) |

Agrégations en Python à partir des services publics (`source_logs.count_source_logs_per_event_day`,
`incidents.incident_statistics.compute_incident_statistics`) : identiques sur PostgreSQL et SQLite, suffisantes pour
les volumes V1. À passer en SQL si les volumes augmentent.
