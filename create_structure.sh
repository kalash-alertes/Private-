#!/usr/bin/env bash
set -Eeuo pipefail

# Crée l'arborescence Kwatsur sans écraser les fichiers existants.
# Usage :
#   chmod +x create_kwatsur_structure.sh
#   ./create_kwatsur_structure.sh [chemin-cible]
#
# Exemple :
#   ./create_kwatsur_structure.sh ./kwatsur

TARGET="${1:-./kwatsur}"

if [[ -e "$TARGET" && ! -d "$TARGET" ]]; then
  echo "Erreur : '$TARGET' existe mais n'est pas un dossier." >&2
  exit 1
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

create_dir() {
  mkdir -p "$TARGET/$1"
}

write_if_missing() {
  local relative_path="$1"
  local content="$2"
  local full_path="$TARGET/$relative_path"

  mkdir -p "$(dirname "$full_path")"
  if [[ -e "$full_path" ]]; then
    echo "Conservé (existe déjà) : $relative_path"
  else
    printf '%s' "$content" > "$full_path"
    echo "Créé : $relative_path"
  fi
}

# Dossiers
for dir in \
  app/core app/api/routes app/schemas app/models app/repositories app/services app/jobs \
  app/integrations/llm app/integrations/data app/integrations/agent_runtime \
  app/db \
  db/migrations/versions db/seed \
  frontend/public/assets/avatars frontend/public/assets/images frontend/public/css \
  frontend/public/js/components frontend/public/js/core frontend/public/js/pages \
  frontend/public/js/services/api frontend/public/js/utils \
  tests/unit tests/integration tests/e2e scripts docs
do
  create_dir "$dir"
done

# Fichiers de départ (vides ou avec un court en-tête).
write_if_missing "app/main.py" '"""Point d’entrée de l’application FastAPI."""'$'\n'
write_if_missing "app/core/config.py" '"""Chargement et validation de la configuration."""'$'\n'
write_if_missing "app/core/logging.py" '"""Configuration centralisée des journaux."""'$'\n'
write_if_missing "app/core/exceptions.py" '"""Exceptions applicatives et gestion des erreurs."""'$'\n'
write_if_missing "app/api/dependencies.py" '"""Dépendances FastAPI et injection des services."""'$'\n'
write_if_missing "app/api/routes/chat.py" '"""Routes HTTP pour les conversations."""'$'\n'
write_if_missing "app/api/routes/properties.py" '"""Routes HTTP de recherche des logements."""'$'\n'
write_if_missing "app/api/routes/health.py" '"""Route de contrôle de santé."""'$'\n'
write_if_missing "app/schemas/chat.py" '"""Schémas Pydantic des conversations."""'$'\n'
write_if_missing "app/schemas/property.py" '"""Schémas Pydantic des logements."""'$'\n'
write_if_missing "app/models/property.py" '"""Modèle SQLAlchemy du logement."""'$'\n'
write_if_missing "app/models/conversation.py" '"""Modèle SQLAlchemy de conversation."""'$'\n'
write_if_missing "app/models/message.py" '"""Modèle SQLAlchemy de message."""'$'\n'
write_if_missing "app/repositories/property_repository.py" '"""Accès aux données des logements."""'$'\n'
write_if_missing "app/repositories/conversation_repository.py" '"""Accès aux conversations persistées."""'$'\n'
write_if_missing "app/services/agent_service.py" '"""Orchestration de l’agent."""'$'\n'
write_if_missing "app/services/search_service.py" '"""Recherche et filtrage des logements."""'$'\n'
write_if_missing "app/services/ranking_service.py" '"""Classement explicable des résultats."""'$'\n'
write_if_missing "app/services/conversation_service.py" '"""Gestion des conversations."""'$'\n'
write_if_missing "app/jobs/__init__.py" '"""Tâches planifiées ou exécutées en arrière-plan."""'$'\n'
write_if_missing "app/integrations/llm/base.py" '"""Contrat commun des fournisseurs IA."""'$'\n'
write_if_missing "app/integrations/llm/nemotron.py" '"""Adaptateur Nemotron à implémenter selon la documentation."""'$'\n'
write_if_missing "app/integrations/data/zetaris.py" '"""Adaptateur Zetaris à implémenter selon les accès réels."""'$'\n'
write_if_missing "app/integrations/agent_runtime/meterless.py" '"""Adaptateur Meterless à implémenter selon les outils disponibles."""'$'\n'
write_if_missing "app/db/session.py" '"""Configuration des sessions SQLAlchemy."""'$'\n'
write_if_missing "app/db/base.py" '"""Base déclarative SQLAlchemy."""'$'\n'
write_if_missing "frontend/public/index.html" '<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kwatsur — recherche de logements</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>
  <main id="app">
    <h1>Kwatsur</h1>
    <p>Structure initiale — interface à développer.</p>
  </main>
  <script type="module" src="/js/app.js"></script>
</body>
</html>
'
write_if_missing "frontend/public/css/styles.css" '/* Styles de l’interface Kwatsur. */'$'\n'
write_if_missing "frontend/public/js/app.js" '// Point d’entrée JavaScript du frontend.'$'\n'
write_if_missing "frontend/public/js/components/chat.js" '// Composant d’interface de conversation.'$'\n'
write_if_missing "frontend/public/js/components/property_cards.js" '// Composant d’affichage des cartes de logements.'$'\n'
write_if_missing "requirements.txt" 'fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg[binary]==3.2.3
alembic==1.13.3
pydantic==2.9.2
pydantic-settings==2.6.0
pytest==8.3.3
httpx==0.27.2
'
write_if_missing ".env.example" '# Exemple sans secrets réels.
DATABASE_URL=postgresql+psycopg://postgres:change_me@db:5432/kwatsur
NEMOTRON_BASE_URL=
NEMOTRON_API_KEY=
ZETARIS_BASE_URL=
ZETARIS_API_KEY=
'
write_if_missing ".gitignore" '.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.DS_Store
'
write_if_missing "Dockerfile" 'FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY db ./db
COPY frontend/public ./frontend/public
COPY alembic.ini .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'
write_if_missing "docker-compose.yml" 'services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-kwatsur}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-kwatsur_dev}
      POSTGRES_DB: ${POSTGRES_DB:-kwatsur}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - kwatsur_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-kwatsur} -d ${POSTGRES_DB:-kwatsur}"]
      interval: 5s
      timeout: 5s
      retries: 10
  api:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-kwatsur}:${POSTGRES_PASSWORD:-kwatsur_dev}@db:5432/${POSTGRES_DB:-kwatsur}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:8080}
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
volumes:
  kwatsur_pgdata:
'
write_if_missing "alembic.ini" '[alembic]
script_location = db/migrations
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql+psycopg://kwatsur:kwatsur_dev@localhost:5432/kwatsur
'

write_if_missing "README.md" '# Kwatsur

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
'

write_if_missing "architecture.tree" 'Kwatsur/
├── app/                         # Backend Python
│   ├── api/
│   │   └── routes/
│   ├── core/
│   ├── db/                      # Connexion et sessions runtime
│   ├── integrations/
│   │   ├── agent_runtime/
│   │   ├── data/
│   │   └── llm/
│   ├── jobs/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   └── services/
├── db/                          # Migrations et données initiales
│   ├── migrations/
│   │   └── versions/
│   └── seed/
├── docs/                        # Documentation du projet
├── frontend/                    # Interface web
│   └── public/
│       ├── assets/
│       │   ├── avatars/
│       │   └── images/
│       ├── css/
│       └── js/
│           ├── components/
│           ├── core/
│           ├── pages/
│           ├── services/
│           │   └── api/
│           └── utils/
├── scripts/                     # Outils de développement
└── tests/
    ├── e2e/
    ├── integration/
    └── unit/
'

# README in every directory; do not overwrite existing docs.
declare -A DIR_DOCS
DIR_DOCS["app"]="Backend Python de Kwatsur : API, cas d’usage, accès aux données et adaptateurs, rangés selon leur responsabilité."
DIR_DOCS["app/core"]="Configuration, journaux et exceptions partagés. Ne place pas ici la logique métier de recherche."
DIR_DOCS["app/api"]="Couche HTTP FastAPI. Les routes valident les requêtes et appellent les services ; elles ne portent pas la logique métier complète."
DIR_DOCS["app/api/routes"]="Contrôleurs HTTP par domaine. Retourne des réponses HTTP cohérentes et délègue les opérations aux services."
DIR_DOCS["app/schemas"]="Contrats Pydantic pour valider les entrées et sorties. À distinguer des modèles SQLAlchemy."
DIR_DOCS["app/models"]="Entités SQLAlchemy et relations de persistance. Pas d’appels réseau ni d’orchestration dans les modèles."
DIR_DOCS["app/repositories"]="Centralise les lectures et écritures en base. Évite les requêtes SQL dispersées dans les routes et services."
DIR_DOCS["app/services"]="Cas d’utilisation et logique métier : recherche, classement, conversations et orchestration de l’agent."
DIR_DOCS["app/jobs"]="Tâches planifiées ou exécutées en arrière-plan. Garde ce dossier vide tant qu’aucun besoin concret n’existe."
DIR_DOCS["app/integrations"]="Adaptateurs des fournisseurs externes. N’annonce une intégration active qu’après validation réelle."
DIR_DOCS["app/integrations/llm"]="Contrats et adaptateurs des fournisseurs de langage. N’invente ni endpoint ni modèle."
DIR_DOCS["app/integrations/data"]="Adaptateurs de données autorisés. Normalise les résultats et conserve leur provenance."
DIR_DOCS["app/integrations/agent_runtime"]="Adaptateur de moteur d’agent lorsque les outils et accès sont officiellement disponibles."
DIR_DOCS["app/db"]="Configuration SQLAlchemy, sessions et base déclarative. Les requêtes propres aux logements restent dans les repositories."
DIR_DOCS["frontend"]="Interface web. Les pages et ressources servies au navigateur se trouvent dans public/."
DIR_DOCS["db"]="Migrations PostgreSQL et données d’initialisation. La connexion runtime reste dans app/db."
DIR_DOCS["db/migrations"]="Historique des changements de schéma géré par Alembic. Versionne les évolutions de base."
DIR_DOCS["db/migrations/versions"]="Fichiers de migration versionnés. Vérifie les fonctions upgrade et downgrade."
DIR_DOCS["db/seed"]="Données et scripts d’initialisation pour les environnements de développement, test ou démonstration."
DIR_DOCS["frontend/public"]="Pages et ressources statiques exposées au navigateur. N’y place aucun secret ou code serveur."
DIR_DOCS["frontend/public/assets"]="Images, icônes, avatars et autres ressources visuelles."
DIR_DOCS["frontend/public/assets/avatars"]="Avatars fictifs ou génériques. Ne stocke pas de photos personnelles sans autorisation."
DIR_DOCS["frontend/public/assets/images"]="Images et illustrations statiques utilisées par les pages."
DIR_DOCS["frontend/public/css"]="Styles, mise en page responsive et états visuels. Pas de logique métier."
DIR_DOCS["frontend/public/js"]="Modules JavaScript de l’interface. Les règles métier restent côté serveur."
DIR_DOCS["frontend/public/js/components"]="Composants d’interface réutilisables, chacun centré sur une responsabilité visuelle."
DIR_DOCS["frontend/public/js/core"]="Fonctions techniques frontend partagées, sans secrets côté client."
DIR_DOCS["frontend/public/js/pages"]="Initialisation et comportement propres à chaque page HTML."
DIR_DOCS["frontend/public/js/services"]="Services client qui coordonnent les échanges avec l’API et l’état local."
DIR_DOCS["frontend/public/js/services/api"]="Emplacement des clients HTTP par ressource ; le MVP utilise fetch directement depuis app.js."
DIR_DOCS["frontend/public/js/utils"]="Fonctions utilitaires frontend réutilisables et indépendantes des pages."
DIR_DOCS["tests"]="Tous les tests automatisés. Les tests doivent être reproductibles et documenter leurs prérequis."
DIR_DOCS["tests/unit"]="Tests isolés des règles métier avec dépendances simulées."
DIR_DOCS["tests/integration"]="Tests des interactions entre composants et base de test. Les appels externes doivent être explicitement configurés."
DIR_DOCS["tests/e2e"]="Scénarios complets du parcours utilisateur, documentés et reproductibles."
DIR_DOCS["scripts"]="Scripts répétables d’initialisation, maintenance ou démonstration. Évite les actions destructrices non confirmées."
DIR_DOCS["docs"]="Décisions d’architecture, diagrammes et procédures techniques. Maintiens la documentation alignée sur le code."

for dir in "${!DIR_DOCS[@]}"; do
  folder_name="$(basename "$dir")"
  content="# ${folder_name} — rôle du dossier

${DIR_DOCS[$dir]}

## Règles de contribution

- Garde ce dossier centré sur sa responsabilité.
- Utilise des noms explicites et des interfaces simples.
- Ajoute ou adapte les tests lorsque le comportement change.
- Mets à jour cette documentation si le rôle du dossier évolue.
"
  write_if_missing "$dir/${folder_name}_readme.md" "$content"
done

# Add Python package markers where useful, without overwriting.
for pkg in app app/core app/api app/api/routes app/schemas app/models app/repositories app/services app/jobs app/integrations app/integrations/llm app/integrations/data app/integrations/agent_runtime app/db; do
  write_if_missing "$pkg/__init__.py" ""
done

echo
echo "Structure Kwatsur créée dans : $TARGET"
echo "Les fichiers existants ont été conservés. Consulte README.md avant de commencer le développement."
