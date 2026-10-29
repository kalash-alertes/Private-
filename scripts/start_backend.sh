#!/bin/sh
# Démarrage du conteneur backend : vérifie que le code est lisible, applique les migrations, lance l'application.
#
# Pourquoi la vérification : si le projet est dans un dossier partagé VirtualBox (/media/sf_...), les fichiers montés
# appartiennent au groupe vboxsf (droits 0770) et sont illisibles pour le compte du conteneur. Sans ce test, Alembic
# échoue avec un message obscur (« No 'script_location' key found in configuration »).
set -e

for required_file in alembic.ini backend/main.py db/migrations/env.py web_interface/web_interface_registration.py; do
    if [ ! -r "$required_file" ]; then
        echo "ERREUR : le fichier $required_file est illisible dans le conteneur (compte : $(id -un))."
        echo "Cause probable : projet placé dans un dossier partagé VirtualBox (droits du groupe vboxsf)."
        echo "Solutions : cloner le projet sur le disque de la machine virtuelle (recommandé),"
        echo "ou mettre BACKEND_CONTAINER_USER=root dans le .env. Voir docs/overview/running_the_application.md."
        exit 1
    fi
done

alembic upgrade head
exec uvicorn backend.main:application --host 0.0.0.0 --port 8000 --reload
