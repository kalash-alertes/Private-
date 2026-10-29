# Comment exécuter l'application

Tout tourne dans **deux conteneurs Docker** : la base de données (PostgreSQL) et l'application (le « backend », qui
sert aussi l'interface). Sur ce poste, Docker fonctionne dans **WSL** : chaque commande `docker` est donc précédée
de `wsl`.

Toutes les commandes se tapent dans **PowerShell**, depuis le dossier du projet :

```powershell
cd F:\shared_folder\Intelligentsia_SOC
```

---

## 1. La toute première fois (une seule fois)

```powershell
# 1. Créer le fichier de configuration à partir du modèle
Copy-Item .env.example .env

# 2. Télécharger les paquets Python pour Docker (depuis Windows, voir « Pourquoi » plus bas)
powershell -File scripts\download_docker_wheels.ps1

# 3. Construire l'image et démarrer les deux conteneurs
wsl docker compose up --build -d
```

Au démarrage, l'application **crée ou met à jour les tables automatiquement** (migrations Alembic) : rien à faire.

> **Pourquoi l'étape 2 ?** Depuis Docker sous WSL, les téléchargements Python (PyPI) se coupent en plein fichier.
> Windows, lui, télécharge sans problème : le script met les paquets dans `docker_wheels/`, et Docker les installe
> depuis ce dossier, sans Internet.

---

## 2. Tous les jours

| Je veux… | Commande |
|---|---|
| **Démarrer** | `wsl docker compose up -d` |
| **Arrêter** (les données sont conservées) | `wsl docker compose down` |
| Voir si ça tourne | `wsl docker compose ps` |
| Lire les messages de l'application | `wsl docker compose logs -f backend` (`Ctrl+C` pour quitter) |
| Redémarrer l'application seule | `wsl docker compose restart backend` |

Pendant le développement, le code du dossier est **monté dans le conteneur** et l'application **redémarre toute seule**
quand un fichier Python change : pas besoin de reconstruire l'image pour voir une modification.

**Reconstruire l'image** (`--build`) seulement si `requirements.txt` ou le `Dockerfile` change :

```powershell
powershell -File scripts\download_docker_wheels.ps1   # seulement si requirements.txt a changé
wsl docker compose up --build -d
```

---

## 3. Ouvrir l'application

| Quoi | Adresse |
|---|---|
| **Interface des analystes** | http://localhost:8000 |
| Documentation interactive de l'API (tester les routes) | http://localhost:8000/docs |
| API JSON | http://localhost:8000/api/... (ex. http://localhost:8000/api/health) |
| Base PostgreSQL (outil comme DBeaver, pgAdmin) | `localhost:5432`, base `soc_incidents`, utilisateur et mot de passe dans `.env` |

---

## 4. Voir des données de test (démonstration)

Avec `APP_IS_IN_DEMO=true` (valeur par défaut du `.env`), l'application **invente quelques alertes à chaque collecte**
(toutes les 5 minutes, ou bouton « Lancer une collecte maintenant » dans **Journaux**). Un badge « DÉMO » est affiché
en haut. Pour lire le vrai FortiAnalyzer : [connecting_fortianalyzer.md](./connecting_fortianalyzer.md).

En plus, pour remplir tous les écrans d'un coup (playbooks, incidents à différents stades) :

Tant que le collecteur FortiAnalyzer n'est pas branché, la base est vide. Pour voir les écrans remplis :

```powershell
wsl docker compose exec backend python -m scripts.load_synthetic_demo_data
```

Puis rafraîchir http://localhost:8000. Le script crée :

| Élément | Contenu |
|---|---|
| 3 playbooks | intrusion, malware, phishing (marqués « démonstration », ce ne sont **pas** de vraies procédures) |
| 8 alertes | identifiants commençant par `SYNTHETIQUE-DEMO-`, sévérités variées |
| 6 incidents | 4 **en cours** (nouveau, en cours, en attente), 2 **traités** (résolu, clôturé), avec des étapes cochées |
| 2 alertes sans incident | visibles dans **Alertes** avec le bouton « Créer l'incident » |
| 1 import | visible dans **Journaux** |
| Événements | visibles dans **Paramètres > Journal d'audit** |

Ces données sont **inventées**. Relancer le script ne crée pas de doublons d'alertes. Le script refuse de s'exécuter si `APP_IS_IN_DEMO=false` (base alimentée par le vrai FortiAnalyzer).

**À essayer** pour faire le tour :
1. **Incidents** : passer de l'onglet « En cours » à « Traités », filtrer, chercher.
2. Cliquer sur un incident : son **playbook** s'affiche, cocher une étape (« Fait »).
3. **Alertes** : créer l'incident d'une alerte restante.
4. **Paramètres > Réponse aux incidents** : mettre « critique » à 1 minute, activer l'escalade, attendre une minute,
   puis cliquer sur « Lancer l'escalade maintenant » : les incidents critiques en retard sont escaladés.
5. **Paramètres > Journal d'audit** : retrouver tout ce qui vient d'être fait.

---

## 5. Repartir d'une base vide

```powershell
wsl docker compose down -v      # ATTENTION : -v supprime DÉFINITIVEMENT toutes les données de la base
wsl docker compose up -d        # recrée une base vide (tables recréées automatiquement)
```

Sans `-v`, `down` arrête simplement les conteneurs et garde les données.

---

## 6. Lancer les tests

Les tests n'ont besoin ni de Docker ni de PostgreSQL (ils utilisent une base temporaire SQLite).
Ils tournent avec le Python de Windows :

```powershell
python -m pip install -r requirements.txt   # une seule fois (et après un changement de requirements.txt)
python -m pytest
```

Résultat attendu : tous les tests passent ; quelques-uns sont « skipped » (ceux qui demandent un PostgreSQL de test
dédié, voir [docs/technical/testing.md](../technical/testing.md)).

---

## 7. En cas de problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| La page ne répond plus après une pause | WSL s'est arrêté (inactivité) et a coupé les conteneurs | `wsl docker compose up -d` |
| La page ne répond pas juste après le démarrage | L'application démarre encore (quelques secondes) | Attendre puis rafraîchir ; vérifier `wsl docker compose logs backend` |
| Construction : `Read timed out` ou `from versions: none` | Téléchargement PyPI coupé dans Docker | `powershell -File scripts\download_docker_wheels.ps1` puis `wsl docker compose up --build -d` |
| Construction : un paquet manque (ex. `uvloop`) | Paquet réservé à Linux, ignoré par pip sous Windows | L'ajouter dans `scripts/download_docker_wheels.ps1` (comme `uvloop`) et relancer le script |
| `pip install` sous Windows : version introuvable | Version qui n'existe pas pour Python 3.14 | Choisir une version disponible pour 3.12 **et** 3.14 dans `requirements.txt` |
| `No 'script_location' key found in configuration`, ou « fichier … illisible dans le conteneur » | Projet dans un **dossier partagé VirtualBox** (`/media/sf_...`) : ses fichiers sont réservés au groupe `vboxsf`, illisibles pour le compte du conteneur | **Recommandé** : cloner le projet sur le disque de la machine virtuelle (`git clone` dans le dossier personnel), puis `docker compose up --build -d`. Sinon : `BACKEND_CONTAINER_USER=root` dans le `.env` |
| Rien ne correspond, ou `alembic.ini` absent | Mauvaise branche : `main` contient l'ancienne version | `git checkout feature/fortianalyzer-collector` |
| `port is already allocated` (5432 ou 8000) | Un autre programme utilise le port | Arrêter ce programme, ou changer `POSTGRES_PORT` dans `.env` |
| Erreur de base après avoir changé le code des tables | Une migration manque | Voir [docs/technical/database.md](../technical/database.md) (« Modifier le schéma ») |

---

## Rappel important

L'application **n'a pas encore de connexion des utilisateurs** : elle ne doit pas être ouverte en dehors de ce poste
(les ports ne sont accessibles que depuis la machine elle-même).
