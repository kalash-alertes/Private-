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

## Stockage : un fichier JSON par playbook, la base comme index

Décision du 03/11/2026 (demande de l'équipe) : un playbook est d'abord un **fichier JSON lisible** dans
`PLAYBOOK_FILES_DIRECTORY` (défaut `db/playbooks/`, relatif à la racine du projet) ; les tables `playbooks` /
`etapes_playbook` en sont l'index (recherche, lien avec les incidents, suivi des étapes cochées). Aucune migration
n'insère de playbook : ils entrent en base par le service, depuis l'interface ou depuis leurs fichiers.

- **Format** (`playbook_files.py`) : `id`, `nom`, `categorie`, `description`, `source`, `etapes[{id, titre,
  description}]`. Un texte sur plusieurs lignes est écrit en **liste de lignes** (lisible), une ligne seule en texte.
  `extra="forbid"` : une clé inconnue (faute de frappe) refuse le fichier. Nom du fichier dérivé du nom du playbook
  (`playbook_file_names.py` : minuscules, sans accents, tirets) ; le lien fichier ↔ base est l'`id` contenu dans le
  fichier, pas le nom de fichier (renommer le playbook renomme le fichier).
- **Écritures depuis l'interface/API** (`create_playbook`, `update_playbook`, `delete_playbook`) : contrôles de la base
  (flush) → écriture atomique du fichier (temporaire puis `os.replace`) → commit. Fichier non écrit (droits, disque) ⇒
  rollback et `BusinessRuleViolationError` (422) ; commit refusé ⇒ fichier remis dans son état précédent
  (`restore_files`). Fichiers et base restent alignés.
- **Synchronisation** `synchronize_playbooks_with_files` (au démarrage de l'application, bouton « Synchroniser avec
  les fichiers » = `POST /parametres/playbooks/synchroniser`, script `python -m scripts.synchronize_playbook_files`) :
  - fichier dont l'`id` est inconnu (ou, sans `id`, dont le nom est inconnu) ⇒ playbook créé avec cet `id`, fichier
    complété (ids des étapes) et renommé ;
  - fichier différent de la base ⇒ `update_playbook` (étapes conservées par `id`, donc leur suivi dans les incidents ;
    une étape sans `id` est nouvelle, une étape absente est supprimée avec son suivi) ;
  - playbook en base sans fichier ⇒ fichier écrit. Un fichier supprimé à la main ne supprime donc PAS le playbook
    (des incidents peuvent l'utiliser) : supprimer passe par l'interface ;
  - fichier invalide (JSON, schéma, nom ou catégorie déjà pris…) ⇒ ignoré, motif journalisé et affiché (422 sur la
    page) ; les autres fichiers sont traités. Chaque changement est audité (acteur « synchronisation des fichiers de
    playbooks »).
- **Tests** : `PLAYBOOK_FILES_DIRECTORY` pointe vers un dossier temporaire par test (`tests/conftest.py`).

## Playbooks de référence fournis

`db/playbooks/` contient 13 procédures publiques et sourcées : 12 fiches IRM (CERT Société Générale, traduction
CERT aDvens, CC BY 3.0), produites par `scripts/build_reference_playbooks_from_cert_irm.py` (API GitHub
`repos/cert-advens/IRM/contents/FR`, extraction PyMuPDF, une phase = une étape, découpe aux sous-titres au-delà de
9 500 caractères, texte non réécrit, `id` existants conservés) ; et ATT&CK T1110 force brute (traduction de MITRE
ATT&CK + NIST SP 800-61 Rév. 2 §3.4.1), rédigé à la main. Correspondance catégorie ↔ sous-type FortiGate (choix de
l'application, modifiable dans les fichiers) : `virus` → IRM-07, `ips` → IRM-05, `anomaly` → IRM-04, `dlp` → IRM-11,
`vpn` → T1110 ; les autres ont des catégories explicites (`ransomware`, `phishing`…).

## Fonctions publiques

`find_playbook_id_for_category` (attribution automatique à la création d'un incident), `fetch_playbook_detail`,
`fetch_playbook_details_by_ids` (une requête pour toute une page d'incidents).
