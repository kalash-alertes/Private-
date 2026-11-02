# Règles pour les IA (et humains) qui codent dans ce projet

Lis ce fichier **avant** de modifier du code. Contexte produit : [explain_project.md](./explain_project.md).
Architecture technique : [docs/technical/architecture.md](./docs/technical/architecture.md).

## 1. Nommage : clair, intuitif, quitte à être long

- Un nom doit dire ce que fait la chose sans lire son code. La longueur n'est pas un problème.
- Fichiers, dossiers, variables, fonctions, classes, routes, tables, colonnes : tous explicites.
  - Bon : `mark_incident_as_false_positive`, `import_run_repository.py`, `source_log_identifier`.
  - Mauvais : `process()`, `data`, `tmp`, `helper.py`, `utils2.py`, `x`, `res`.
- Pas d'abréviations obscures (`cnt`, `mgr`, `cfg`). Pas de phrases entières non plus (`this_is_the_function_that_does_x`).
- Fonction = verbe (`fetch_critical_logs_page`), classe/table = nom (`Incident`), booléen = `is_/has_/can_`.
- Le vocabulaire **métier** de la base suit `explain_project.md` (français : `incidents`, `statut`, `criticite_source`...).
  Le code technique (fonctions, classes, fichiers) est en anglais.

## 2. Modularité : une fonctionnalité = un module indépendant

- Chaque fonctionnalité vit dans `backend/features/<nom_de_la_fonctionnalite>/` et peut être modifiée ou remplacée seule.
- Structure type d'une fonctionnalité :
  `models.py` (tables) · `schemas.py` (entrées/sorties API) · `repository.py` (accès DB) · `service.py` (règles métier) · `router.py` (routes HTTP) · `README.md`.
- Dépendances autorisées : une feature peut dépendre de `backend/core/`. Une feature **n'importe jamais le code interne d'une autre feature** ;
  elle passe par la fonction publique de son `service.py` ou par une clé étrangère.
- `router.py` ne contient pas de logique métier : il appelle `service.py`. `service.py` ne fait pas de SQL : il appelle `repository.py`.
- Les services externes (FortiAnalyzer, OpenSearch, ...) sont isolés dans `backend/integrations/<nom>/` derrière une interface claire,
  pour pouvoir les remplacer ou les simuler dans les tests.
- Un fichier fait une chose. Si un fichier devient difficile à lire d'un coup, découpe-le.

## 3. Commentaires : clairs, précis, aux endroits stratégiques

- Ne commente pas l'évident. Commente le **pourquoi** : règle métier, contrainte, piège, décision non évidente.
- Endroits stratégiques : début de chaque module (docstring de rôle), règles métier, déduplication, gestion d'erreur, contraintes DB, tout contournement.
- Docstring courte sur chaque fonction publique : ce qu'elle fait, ce qu'elle retourne, ce qu'elle lève.

## 4. Documentation : obligatoire pour chaque ajout

Chaque ajout ou changement met à jour **les deux** types de documentation, dans le même commit :

1. **Doc technique** (`docs/technical/`) : détaillée, pour développeurs/IA : fonctionnement interne, tables, endpoints, flux, cas limites, décisions.
2. **Doc humaine** (`docs/overview/`) : vue d'ensemble en langage simple (à quoi ça sert, comment ça s'intègre, ce que l'utilisateur en retire),
   sans jargon inutile, lisible en moins de 5 minutes.
3. Le `README.md` du dossier de la fonctionnalité reste à jour (rôle, fichiers, comment tester).

Une fonctionnalité n'est pas « terminée » tant que ses deux docs et ses tests ne sont pas écrits.

## 5. Base de données

- Toute modification de schéma passe par une migration Alembic dans `db/migrations/versions/`. Jamais de modification manuelle.
- Dates en `TIMESTAMPTZ` (UTC). Clés primaires en UUID. Contraintes (statuts, criticités, unicité) déclarées en base, pas seulement dans le code.
- Imports idempotents : réimporter le même log ne crée jamais de doublon.
- La criticité source (FortiAnalyzer) n'est **jamais** écrasée ; la criticité réévaluée est un champ séparé.

## 6. Sécurité

- Aucun secret en dur ni dans les logs. Tout passe par variables d'environnement (`.env`, jamais commité ; modèle : `.env.example`).
- Valider toute donnée externe (syslog FortiAnalyzer, requêtes HTTP) avec Pydantic.
- Aucune action destructrice automatique sur l'infrastructure.
- Ne jamais présenter une procédure de réponse inventée comme vérité : toute procédure cite sa source.

## 7. Tests

- Toute fonctionnalité a des tests dans `tests/` (miroir de la structure `backend/`). Lancer : `pytest`.
- Les intégrations externes sont testées avec des faux (fakes), jamais avec de vrais appels réseau.

## 8. Avant de finir une tâche

- [ ] Noms explicites · [ ] Module indépendant · [ ] Commentaires utiles · [ ] Doc technique + doc humaine · [ ] Migration si DB · [ ] Tests verts
