# Brancher l'application sur FortiAnalyzer

FortiAnalyzer **envoie lui-même** ses logs à l'application, par le protocole **syslog** (fonction « Log Forwarding »).
L'application se contente d'**écouter** un port réseau : pas d'identifiant, pas de mot de passe, pas de jeton.

Une seule ligne du fichier `.env` choisit d'où viennent les alertes :

| `APP_IS_IN_DEMO=` | D'où viennent les alertes |
|---|---|
| `true` (par défaut) | **Démonstration** : quelques alertes **inventées** à chaque collecte. Aucun port n'est écouté. Un badge « DÉMO » est affiché en haut de l'écran. |
| `false` | **Le vrai FortiAnalyzer**, qui transfère ses logs vers le port d'écoute (5140 par défaut). |

Dans les deux cas, la suite est identique : les alertes arrivent dans **Alertes**, chaque collecte est inscrite dans
**Journaux**, et on crée les incidents comme d'habitude.

---

## Comment ça marche, en bref

1. FortiAnalyzer envoie chaque log, dès qu'il le reçoit, vers l'adresse du poste, port 5140.
2. L'application les garde **en attente** dans sa mémoire.
3. Toutes les 30 secondes (réglable), une **collecte** enregistre ceux qui sont assez graves (par défaut « haute » et
   « critique ») dans la base. Les autres sont lus puis écartés.
4. Une collecte où rien n'est arrivé n'apparaît pas dans Journaux (pour ne pas remplir l'historique de lignes vides).

## 1. Configurer FortiAnalyzer (administrateur FortiAnalyzer)

Dans **System Settings > Advanced > Log Forwarding**, créer un transfert :
- **Server Type** : Syslog ; **Server Address** : l'adresse IP du poste qui fait tourner l'application ;
- **Server Port** : `5140` (ou la valeur de `SYSLOG_LISTEN_PORT`) ;
- protocole UDP (par défaut) ou TCP : les deux sont écoutés ;
- choisir les équipements / types de logs à transférer (le filtrage par sévérité est de toute façon fait par l'application).

Le script `tests/test_connection_fortianlyzer_by_syslog.py` permet de vérifier, **application arrêtée**, que les
messages arrivent bien sur le poste (il utilise le même port).

## 2. Remplir le fichier `.env`

Ouvrir `F:\shared_folder\Intelligentsia_SOC\.env` (jamais envoyé sur GitHub) :

```ini
APP_IS_IN_DEMO=false
LOG_COLLECTION_INTERVAL_SECONDS=30

SYSLOG_LISTEN_PORT=5140
# Recommandé : n'accepter que FortiAnalyzer (adresse vue par l'application, voir plus bas)
SYSLOG_ALLOWED_SENDER_ADDRESSES=
```

Autres réglages (déjà remplis avec des valeurs par défaut) :

| Variable | Rôle | Défaut |
|---|---|---|
| `LOG_COLLECTION_MINIMUM_CRITICALITY` | Sévérité minimale gardée (`information` → `critique`) | `haute` |
| `SYSLOG_IS_UDP_ENABLED` / `SYSLOG_IS_TCP_ENABLED` | Protocoles écoutés | `true` / `true` |
| `SYSLOG_LISTEN_ADDRESS` | Interface écoutée | `0.0.0.0` (toutes) |
| `SYSLOG_MAXIMUM_PENDING_LOGS` | Logs en attente au maximum ; au-delà, ils sont perdus | `100000` |
| `FORTIANALYZER_TIMEZONE` | Fuseau de secours pour dater un log (rarement utile) | `UTC` |

Les anciennes variables de connexion à l'API (`FORTIANALYZER_BASE_URL`, `FORTIANALYZER_API_TOKEN`…) ne servent plus :
on peut les supprimer du `.env`.

## 3. Le réseau : laisser entrer les logs jusqu'à l'application

L'application tourne dans Docker, lui-même dans WSL. Les logs de FortiAnalyzer doivent traverser : **réseau → Windows →
WSL → conteneur**.

- **Pare-feu Windows** : autoriser l'entrée sur le port 5140 en UDP et TCP.
- **WSL** : par défaut, WSL ne reçoit pas le trafic qui vient d'autres machines. Le plus simple est le mode réseau
  « mirrored » : dans `C:\Users\<vous>\.wslconfig`, section `[wsl2]`, ajouter `networkingMode=mirrored`, puis
  `wsl --shutdown` et relancer. (Sans ce mode, `netsh interface portproxy` ne transfère que le TCP, pas l'UDP.)
- `docker-compose.yml` publie déjà le port 5140 (UDP et TCP) vers le conteneur.
- WSL s'arrête quand il est inutilisé, et les conteneurs avec lui : garder une fenêtre WSL ouverte pendant les essais.

## 4. Appliquer et vérifier

```powershell
wsl docker compose up -d
```

Puis ouvrir **http://localhost:8000/journaux** :

- l'encadré du haut doit afficher **Réception syslog FortiAnalyzer**, **À l'écoute**, et le badge « Données réelles » ;
- les compteurs « log(s) reçu(s) » et « en attente » augmentent quand FortiAnalyzer envoie ;
- une ligne **Réussie** apparaît dans l'historique à chaque collecte qui a reçu des logs ; les alertes graves sont dans
  **Alertes** ;
- **« Lancer une collecte maintenant »** force une collecte (inscrite même si rien n'est arrivé).

Pour remplir `SYSLOG_ALLOWED_SENDER_ADDRESSES` : ouvrir une alerte reçue, regarder `reception_syslog` →
`adresse_emetteur` dans les données brutes (avec Docker, ce peut être une adresse interne plutôt que celle de
FortiAnalyzer).

Les messages de l'application : `wsl docker compose logs -f backend`.

## 5. En cas de problème

| Ce qu'on voit | Que faire |
|---|---|
| Bandeau rouge « Réception syslog inactive … Impossible d'écouter » | Le port est déjà pris (par exemple par le script de test) : l'arrêter, puis `wsl docker compose up -d`. |
| Bandeau rouge « À corriger dans le fichier .env » | Corriger la variable citée, puis `wsl docker compose up -d`. |
| « À l'écoute » mais 0 log reçu | Les messages n'arrivent pas : vérifier le transfert dans FortiAnalyzer (adresse, port), le pare-feu Windows, le mode réseau de WSL (section 3). |
| Logs « refusé(s) (émetteur non autorisé) » | L'adresse vue par l'application n'est pas dans `SYSLOG_ALLOWED_SENDER_ADDRESSES` : la corriger ou vider la variable. |
| Logs « illisible(s) » | Ce ne sont pas des logs Fortinet (`clé=valeur`) : vérifier le format choisi dans FortiAnalyzer. |
| Logs « perdu(s), file pleine » | La collecte ne suit pas : réduire `LOG_COLLECTION_INTERVAL_SECONDS` ou filtrer davantage côté FortiAnalyzer. |
| Beaucoup de logs reçus, aucune alerte | Normal pour les logs de trafic (sévérité « notice » = faible) : seules les sévérités ≥ `LOG_COLLECTION_MINIMUM_CRITICALITY` sont gardées. |

## 6. À savoir

- Une même alerte n'est **jamais enregistrée deux fois**, même si FortiAnalyzer la renvoie.
- La sévérité d'origine de FortiAnalyzer est conservée telle quelle ; elle peut être réévaluée dans l'incident.
- Les logs **en attente** sont en mémoire : s'ils n'ont pas encore été collectés quand l'application s'arrête, ils sont
  perdus pour l'application (FortiAnalyzer les garde). D'où une collecte toutes les 30 secondes.
- Le syslog n'est ni authentifié ni chiffré : limiter les émetteurs (`SYSLOG_ALLOWED_SENDER_ADDRESSES`) et le pare-feu.
- Revenir à la démonstration : `APP_IS_IN_DEMO=true`, puis `wsl docker compose up -d`. Les alertes réelles déjà
  enregistrées restent en base.
