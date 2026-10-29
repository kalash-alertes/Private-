# Fonctionnalité `playbooks` — procédures de réponse

Code : `backend/features/playbooks/`. Tables : `playbooks`, `etapes_playbook` (voir [database.md](./database.md)).
Interface : Paramètres > Réponse aux incidents > Playbooks (`/parametres/playbooks`).

## Routes HTTP (API)

| Méthode | Route | Corps | Réponse / erreurs |
|---|---|---|---|
| POST | `/api/parametres/playbooks` | `PlaybookWriteRequest` | 201 détail ; 409 nom ou catégorie déjà pris ; 422 |
| GET | `/api/parametres/playbooks?categorie=&limit=&offset=` | — | page triée par nom, avec `nombre_etapes` |
| GET | `/api/parametres/playbooks/{id}` | — | détail avec étapes ordonnées ; 404 |
| PUT | `/api/parametres/playbooks/{id}` | `PlaybookWriteRequest` | détail ; 404 ; 409 ; 422 (étape d'un autre playbook) |
| DELETE | `/api/parametres/playbooks/{id}` | — | 204 ; 404 |

`PlaybookWriteRequest` : `nom` (1–255), `description?`, `categorie?` (1–255), `source` (**obligatoire**, 1–10 000),
`etapes` (1–100 éléments `{id?, titre, description?}`).

## Règles

- **Source obligatoire** (schéma + CHECK) : règle du projet, une procédure n'est jamais présentée sans référence.
- `nom` UNIQUE ; `categorie` UNIQUE quand renseignée (plusieurs `NULL` permis). Vérification préalable pour un message
  clair ; la contrainte UNIQUE reste l'arbitre en cas de concurrence (IntegrityError → 409).
- Étapes : `ordre` = position dans la liste (1..n, sans trou), `UNIQUE(playbook_id, ordre)`, `ordre ≥ 1`.
- **Modification = remplacement de la liste.** Étape envoyée avec son `id` : conservée (son suivi dans les incidents
  aussi) ; sans `id` : créée ; absente : supprimée (avec son suivi, `ON DELETE CASCADE`). Un `id` étranger ⇒ 422.
  Réordonnancement en deux temps (positions décalées de 1 000 000, puis positions finales) pour ne jamais violer
  l'unicité de `ordre` pendant l'écriture.
- Suppression : étapes supprimées (CASCADE) ; les incidents liés passent à `playbook_id = NULL` (`ON DELETE SET NULL`).
- Chaque création / modification / suppression ajoute un événement au journal d'audit, dans la même transaction.

## Fonctions publiques

`find_playbook_id_for_category` (attribution automatique à la création d'un incident), `fetch_playbook_detail`,
`fetch_playbook_details_by_ids` (une requête pour toute une page d'incidents).
