# Fonctionnalité `incidents` — cycle de vie d'un incident

Code : `backend/features/incidents/`. Table : `incidents` (voir [database.md](./database.md)).

## Routes HTTP

| Méthode | Route | Corps | Réponse / erreurs |
|---|---|---|---|
| POST | `/incidents` | `{"log_id": uuid}` | 201 détail ; 404 log absent ; 409 log déjà lié à un incident |
| GET | `/incidents?statut=&criticite_actuelle=&faux_positif=&assigne_a=&log_id=&limit=&offset=` | — | page, plus récents d'abord |
| GET | `/incidents/{id}` | — | détail (+ `criticite_source` du log) ; 404 |
| PUT | `/incidents/{id}/statut` | `{"statut": ...}` | détail ; 404 |
| PUT | `/incidents/{id}/criticite-actuelle` | `{"criticite_actuelle": ...}` | détail ; 404 ; 409 si clôturé |
| PUT | `/incidents/{id}/faux-positif` | `{"faux_positif": bool, "justification": str?}` | détail ; 404 ; 409 si clôturé ; 422 si justification manquante |
| PUT | `/incidents/{id}/assignation` | `{"assigne_a": str \| null}` | détail ; 404 ; 409 si clôturé |

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

**PROVISOIRES (décision attendue)**
- Toutes les transitions de statut sont autorisées (aucun graphe défini dans le cadrage).
- Un incident clôturé est en lecture seule (criticité, faux positif, attribution ⇒ 409) : il faut le rouvrir.
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

`service.py` appelle `backend.features.source_logs.service.fetch_source_log_metadata` (fonction publique) pour lire la
criticité source. Aucun import du code interne de `source_logs`.
