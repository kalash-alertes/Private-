# Kwatsur

Kwatsur est un agent conversationnel de recherche et de comparaison de logements à louer, conçu d’abord pour le marché camerounais.

L’organisation du projet reprend celle de l’ancien projet décrit dans `tree.txt`, en l’adaptant au domaine immobilier.

## Dossiers principaux

- `app/` : backend Python — API, logique métier, données, intégrations et traitements.
- `frontend/` : interface web — pages et ressources servies au navigateur.
- `docs/` : documentation technique et fonctionnelle.
- `db/` : migrations SQL/Alembic et scripts de données initiales (seed).

Les dossiers de support `tests/` et `scripts/` restent à la racine pour faciliter les tests et les commandes du projet.

## Organisation du backend

Le flux principal est `frontend/` → `app/api/` → `app/services/` → `app/repositories/` ou `app/integrations/`.

- `app/api/` reçoit les requêtes HTTP et délègue aux services.
- `app/core/` contient configuration, journalisation et erreurs partagées.
- `app/services/` porte les cas d’utilisation et les règles métier.
- `app/models/` décrit les entités persistées ; `app/schemas/` décrit les contrats d’API.
- `app/repositories/` isole les accès aux données ; `app/db/` gère la connexion et les sessions de la base.
- `app/integrations/` isole les fournisseurs externes ; `app/jobs/` accueillera les tâches en arrière-plan lorsqu’elles seront nécessaires.

Les routes ne portent pas les règles métier, et les services ne dépendent pas des détails HTTP ou des SDK des fournisseurs.

## Documentation et structure

Chaque répertoire contient un README local qui explique son rôle de façon indépendante. Le script `create_kwatsur_structure.sh` crée les dossiers et documentations manquants sans remplacer les fichiers existants.

Consulte `architecture.tree` pour la vue d’ensemble.

## Règles

- Garder chaque module centré sur une responsabilité et choisir des noms explicites.
- Ne pas inventer de données, d’endpoints ou d’intégrations.
- Marquer les données de démonstration comme fictives.
- Garder les secrets dans `.env`, jamais dans Git ni dans le frontend.
- Ajouter ou adapter les tests lors d’un changement de comportement.
