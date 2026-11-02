# Lancer l'application dans une VM Kali (VirtualBox)

Même application, mêmes deux conteneurs Docker que sous Windows. Les différences : les commandes se tapent dans un
terminal Kali **sans `wsl`**, et une VM apporte trois pièges (dossier partagé, `.env` partagé, réseau) expliqués ici.
Guide général : [running_the_application.md](./running_the_application.md).

---

## 1. Prérequis (une seule fois)

```bash
sudo apt update && sudo apt install -y docker.io docker-compose git
sudo usermod -aG docker "$USER"     # puis se déconnecter / reconnecter (sinon : préfixer chaque commande par sudo)
docker compose version              # 2.24 ou plus récente (si « unknown command » : sudo apt install docker-compose-plugin)
```

## 2. Où mettre le projet : cloner sur le disque de la VM (recommandé)

```bash
git clone <adresse du dépôt GitHub> ~/intelligentsia_soc
cd ~/intelligentsia_soc
cp .env.example .env               # .env PROPRE à cette VM (APP_IS_IN_DEMO=true par défaut)
docker compose up --build -d
```

Puis ouvrir http://localhost:8000 dans Firefox (dans la VM).

**Pourquoi ne pas lancer depuis le dossier partagé VirtualBox (`/media/sf_...`) ?**
- **Le `.env` est partagé** : c'est le même fichier pour l'hôte et toutes les VM qui ouvrent ce dossier. Si l'hôte
  est en `APP_IS_IN_DEMO=false` (vrais logs FortiAnalyzer), la VM l'est aussi : **aucune alerte de démonstration**
  n'apparaît, et le script de données de test refuse de s'exécuter.
- **Les droits** : les fichiers appartiennent au groupe `vboxsf`, illisibles pour le compte du conteneur sans réglage
  (voir section 5).

## 3. Voir les données de test

1. Vérifier le mode réellement utilisé par l'application :
   ```bash
   docker compose exec backend printenv APP_IS_IN_DEMO     # doit afficher true
   ```
   En mode démonstration, un bandeau orange rayé « MODE DÉMONSTRATION » est affiché en haut de chaque page, et
   quelques alertes inventées arrivent toutes les 30 secondes.
2. Remplir tous les écrans (playbooks, incidents, journal d'audit) :
   ```bash
   docker compose exec backend python -m scripts.load_synthetic_demo_data
   ```
   Le message attendu est « Données de démonstration chargées (8 nouvelle(s) alerte(s)) ».
3. Rafraîchir http://localhost:8000.

Chaque VM a **sa propre base** (volume Docker de la VM) : les données d'un PC n'apparaissent pas sur un autre.
Après `docker compose down -v` (base supprimée), refaire l'étape 2.

**Si le projet est quand même dans le dossier partagé** et que le `.env` partagé dit `APP_IS_IN_DEMO=false`, forcer la
démonstration pour cette VM seulement, sans modifier le fichier :

```bash
APP_IS_IN_DEMO=true docker compose up -d
docker compose exec backend python -m scripts.load_synthetic_demo_data
```

(À répéter à chaque `docker compose up` : sans la variable, le `.env` reprend la main.)

## 4. Recevoir les vrais logs FortiAnalyzer dans la VM

FortiAnalyzer doit envoyer ses logs (syslog, port 5140) à une adresse **joignable depuis le réseau**. Selon le mode
réseau de la VM (VirtualBox > Configuration > Réseau > Carte 1) :

- **NAT** (par défaut) : la VM est cachée derrière le PC. On donne à FortiAnalyzer **l'adresse IP du PC hôte**, puis
  on ajoute dans VirtualBox (*Avancé > Redirection de ports*) deux règles : UDP 5140 → 5140 et TCP 5140 → 5140.
  Autoriser aussi le port 5140 dans le pare-feu Windows de l'hôte.
- **Accès par pont** (*Bridged*, plus simple si le réseau l'accepte) : la VM a sa propre adresse sur le réseau
  (`ip -4 addr` dans Kali). On donne à FortiAnalyzer **l'adresse de la VM**, rien d'autre à configurer.

Ensuite, dans le `.env` de la VM : `APP_IS_IN_DEMO=false`, puis `docker compose up -d`. Détails, vérification et
dépannage : [connecting_fortianalyzer.md](./connecting_fortianalyzer.md) (section « Si l'application tourne dans une
VM Kali »).

## 5. Dépannage propre aux VM

| Ce qu'on voit | Cause | Solution |
|---|---|---|
| Aucune alerte, pas de bandeau « MODE DÉMONSTRATION » | `APP_IS_IN_DEMO=false` (souvent : `.env` partagé avec l'hôte) | Cloner le projet sur la VM avec son propre `.env` (section 2), ou forcer `APP_IS_IN_DEMO=true` au lancement (section 3) |
| `Refusé : APP_IS_IN_DEMO=false` en chargeant les données de test | Même cause | Même solution |
| « fichier … illisible dans le conteneur » au démarrage | Projet dans `/media/sf_...` et GID de `vboxsf` différent de 968 | `getent group vboxsf` puis `DOCKER_SHARED_GROUP_ID=<GID>` dans le `.env` ; ou `BACKEND_CONTAINER_USER=root` ; ou cloner sur la VM |
| `permission denied ... docker.sock` | Compte pas encore dans le groupe `docker` | Se reconnecter après `usermod -aG docker`, ou préfixer par `sudo` |
| `env_file` / `required` refusé par `docker compose` | Docker Compose trop ancien (< 2.24) | Installer une version récente de `docker-compose` (paquet Kali à jour) |
| « À l'écoute » mais 0 log reçu | FortiAnalyzer vise une adresse injoignable | Revoir la section 4 (NAT : adresse de l'hôte + redirection ; pont : adresse de la VM) |
