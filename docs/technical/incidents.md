# Fonctionnalité `incidents` — cycle de vie d'un incident

Code : `backend/features/incidents/`. Table : `incidents` (voir [database.md](./database.md)).

## Routes HTTP

| Méthode | Route | Corps | Réponse / erreurs |
|---|---|---|---|
Toutes les routes sont sous `/api` (la racine sert l'interface web).

| Méthode | Route | Corps | Réponse / erreurs |
|---|---|---|---|
| POST | `/api/incidents` | `{"log_id": uuid, "titre"?: str, "categorie"?: str}` | 201 détail ; 404 log absent ; 409 log déjà lié à un incident |
| GET | `/api/incidents?vue=en_cours\|traites&recherche=&statut=&criticite_actuelle=&faux_positif=&assigne_a=&categorie=&playbook_id=&log_id=&limit=&offset=` | — | page de lignes de liste, plus récents d'abord |
| GET | `/api/incidents/{id}` | — | détail (+ `criticite_source`, `alertes`) ; 404 |
| PUT | `/api/incidents/{id}/statut` | `{"statut": ...}` | détail ; 404 |
| PUT | `/api/incidents/{id}/criticite-actuelle` | `{"criticite_actuelle": ...}` | détail ; 404 ; 409 si clôturé |
| PUT | `/api/incidents/{id}/titre` | `{"titre": str}` | détail ; 404 ; 409 si clôturé |
| PUT | `/api/incidents/{id}/categorie` | `{"categorie": str}` | détail ; 404 ; 409 si clôturé |
| PUT | `/api/incidents/{id}/faux-positif` | `{"faux_positif": bool, "justification": str?}` | détail ; 404 ; 409 si clôturé ; 422 si justification manquante |
| PUT | `/api/incidents/{id}/assignation` | `{"assigne_a": str \| null}` | détail ; 404 ; 409 si clôturé |
| GET | `/api/incidents/{id}/playbook` | — | playbook + état de chaque étape (`playbook: null` s'il n'y en a pas) ; 404 |
| PUT | `/api/incidents/{id}/playbook` | `{"playbook_id": uuid \| null}` | détail ; 404 (incident ou playbook) ; 409 si clôturé |
| PUT | `/api/incidents/{id}/playbook/etapes/{etape_id}` | `{"realisee": bool, "realisee_par"?: str}` | playbook de l'incident ; 404 étape hors playbook ; 422 sans playbook ; 409 si clôturé |
| POST | `/api/incidents/escalade-automatique` | — | `{nombre_incidents_escalades, incidents_escalades}` |

**Ligne de liste** (`IncidentListItemRead`) = champs stockés + `reference` (`INC-000042`), `est_ouvert`,
`date_limite_traitement`, `delai_depasse`, `nombre_alertes`, `plan` (`{playbook_id, nom, nombre_etapes,
nombre_etapes_realisees}` ou null). Détail = ligne + `criticite_source` + `alertes[]`.
`recherche` : sous-chaîne sans casse dans titre, catégorie, responsable ; `%` et `_` cherchés littéralement.

Une route par action : chaque règle métier reste isolée et testable. Erreurs métier : `{"detail", "error_code"}`
(`resource_not_found`, `resource_conflict`). Validation : 422 au format FastAPI. Champ inconnu dans un corps ⇒ 422.

## Règles appliquées

**Définitives (cadrage)**
- Un incident naît d'un log existant ; `UNIQUE(log_id)` : un incident maximum par log (V1).
- `criticite_actuelle` initialisée avec `logs.criticite_source` ; la criticité source n'est jamais modifiée.
- Faux positif ⇒ justification non vide (schéma + CHECK en base).

**Choix d'implémentation (cohérence des données)**
- `cloture` ⇒ `closed_at = now()` (horloge DB, comme `created_at`, pour garantir `closed_at ≥ created_at`, CHECK).
- Reclôturer un incident déjà clôturé ne change pas `closed_at`.
- Quitter `cloture` = **réouverture** : `closed_at` repasse à NULL (CHECK `closed_at` ⇔ `cloture`).
  **Sans table d'historique, la date de la clôture précédente est perdue.**
- Une demande sans changement effectif (même statut, criticité, responsable) n'émet aucun UPDATE : `updated_at` inchangé.
- Retrait du faux positif : justification facultative ; si absente, l'ancienne est conservée (trace minimale).
  Si fournie, elle remplace l'ancienne. Un seul champ `justification` : pas d'historique des motifs.
- `assigne_a` : texte libre, espaces retirés, 1–255 caractères ; `null` = non assigné ; chaîne vide refusée (schéma + CHECK).
- La qualification faux positif **ne change pas** le statut.

**Ajoutées avec les Paramètres**
- Référence séquentielle `numero_reference` (UNIQUE, max + 1 dans le SAVEPOINT ; collision concurrente ⇒ nouvel essai,
  5 au maximum) affichée `INC-000001`.
- Titre et catégorie : fournis à la création ou déduits du log (`Alerte <type>`, `<type>`), modifiables.
- Playbook : à la création, celui de la catégorie (s'il existe) est attribué ; changer la catégorie ne change pas le
  playbook. L'avancement d'un autre playbook est conservé en base mais ne compte pas.
- `traite_le` : renseigné en devenant résolu/clôturé, conservé de résolu à clôturé, effacé à la réouverture (CHECK).
- « En cours » = nouveau, en_cours, en_attente ; « Traités » = résolu, clôturé.
- Date limite, délai dépassé et escalade : voir [incident_response_settings.md](./incident_response_settings.md).
- Chaque changement effectif est tracé dans le journal d'audit ([audit_journal.md](./audit_journal.md)).
- Cocher/décocher une étape met à jour `updated_at` de l'incident (colonne « Mis à jour »).

**PROVISOIRES (décision attendue)**
- Toutes les transitions de statut sont autorisées (aucun graphe défini dans le cadrage).
- Un incident clôturé est en lecture seule (criticité, faux positif, attribution, titre, catégorie, playbook, étapes
  ⇒ 409) : il faut le rouvrir.
  But : le contenu d'un incident clôturé (base du futur rapport) ne change pas silencieusement.
- Valeurs de statut (`nouveau`, `en_cours`, `en_attente`, `resolu`, `cloture`) et de criticité (`information`, `faible`,
  `moyenne`, `haute`, `critique`) : à confirmer ; tout changement = migration (contraintes CHECK).
- `assigne_a` : identifiant libre en attendant le mécanisme d'authentification (aucune vérification que la personne existe).

## Transactions et concurrence

- Création : insertion dans un SAVEPOINT ; la contrainte `UNIQUE(log_id)` arbitre les créations simultanées ;
  le perdant reçoit 409 et sa session reste utilisable (test PostgreSQL
  `test_concurrent_incident_creations_for_one_log_create_one_incident`).
- Modifications : l'incident est chargé avec `SELECT ... FOR UPDATE`. Deux modifications simultanées sont sérialisées ;
  la seconde applique ses règles sur l'état à jour (ex. deux clôtures ⇒ une seule date, test
  `test_concurrent_closings_keep_a_single_consistent_closing_date`). Pas de détection de « mise à jour perdue » côté
  client (pas de numéro de version) : la dernière écriture l'emporte.
- `updated_at` est mis à jour par l'ORM (`onupdate`) ; une mise à jour SQL directe ne le modifierait pas.

## Dépendances

Services publics utilisés (aucun import du code interne d'une autre feature) : `source_logs` (criticité source,
alertes), `playbooks` (attribution, détail), `incident_response_settings` (délais), `audit_journal` (traçage).
Clés étrangères : `incidents.playbook_id → playbooks` (SET NULL), `etapes_realisees_incident.etape_playbook_id →
etapes_playbook` (CASCADE).
