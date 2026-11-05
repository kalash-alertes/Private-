# Logs bruts et playbooks de référence — vue d'ensemble

## « Pourquoi je vois moins de logs que dans FortiAnalyzer ? »

Parce que l'application **trie** : elle ne garde en base que les alertes de dangerosité **moyenne, haute ou critique**
(réglage `LOG_COLLECTION_MINIMUM_CRITICALITY`). Or l'immense majorité des logs d'un FortiGate est du trafic normal, de
niveau « notice » (faible). Mesure faite le 3 novembre 2026 : **environ 99 logs sur 100 sont en « notice »** et sont
donc volontairement écartés. FortiAnalyzer, lui, les affiche tous.

Ce n'est pas une perte : l'application les **reçoit** bien, elle choisit de ne pas les enregistrer.

## La page « Logs bruts »

Menu **Espace de travail > Logs bruts**. Elle montre, en direct, tout ce que FortiAnalyzer envoie, avant le tri :

- en haut, **Reçus contre enregistrés** : combien de logs sont arrivés, combien sont gardés, combien sont écartés, et
  combien sont **perdus** (ce chiffre doit rester à 0) ; puis un tableau par niveau d'origine (notice, error,
  warning…) qui explique d'où vient l'écart ;
- en dessous, le **flux** : une ligne par log, la plus récente en haut. Un clic sur une ligne la déplie et affiche
  **tous les champs** du log (adresses, ports, action, utilisateur…) et le **texte reçu tel quel**, comme dans Wazuh ;
- des filtres : par criticité, « enregistrés » ou « écartés », et une recherche (une adresse IP, un nom d'équipement…) ;
- un bouton **Pause** pour figer le flux le temps de lire.

Quand vous dépliez un log ou faites défiler la liste, les nouveaux messages ne déplacent plus la ligne que vous lisez.
Pause fige aussi une actualisation déjà en cours ; Reprendre récupère les messages encore disponibles.
Les filtres s'appliquent ensemble et restent actifs pendant les actualisations ; la recherche ignore les majuscules.

La page garde les 2 000 derniers logs en mémoire (environ une minute de trafic) ; rien de cette page n'est écrit en base.

## Retrouver le log d'une alerte

Dans **Alertes**, cliquez sur **Voir le log original** : les champs conservés à la collecte s'affichent avec la
criticité d'origine, les dates et un lien vers l'incident s'il existe. Cette copie reste disponible même si le log
n'est plus dans le flux en mémoire. Le texte syslog exact n'est pas conservé en base ; aucune copie n'est inventée
si les données originales sont absentes.

## Une perte corrigée

La vérification a révélé une petite perte réelle : environ **1,3 %** des logs UDP étaient jetés par le système avant
même d'atteindre l'application, parce que FortiAnalyzer envoie par rafales et que la « boîte aux lettres » réseau était
trop petite. Elle a été agrandie (8 Mo) : depuis, **0 perte** mesurée. Le compteur « perdus » de la page Logs bruts et de
la page Journaux permet de le surveiller.

## Les playbooks : des fichiers lisibles

Chaque playbook est un **fichier JSON** clair dans le dossier `db/playbooks/` du projet (un fichier par playbook, par
exemple `irm-07-malware-sous-windows.json`). On peut l'ouvrir, le lire, le corriger avec un simple éditeur, et le
suivre dans Git. La base de données n'en est que l'**index** : elle sert à les retrouver vite et à les relier aux
incidents.

- Créer, modifier ou supprimer un playbook dans l'interface **écrit aussi son fichier**.
- Un fichier ajouté ou modifié à la main est pris en compte au démarrage de l'application, ou tout de suite avec le
  bouton **Synchroniser avec les fichiers** (page Playbooks). Un fichier mal écrit est signalé, avec son nom et l'erreur,
  sans bloquer les autres.
- Supprimer un fichier à la main ne supprime pas le playbook (il peut être utilisé par des incidents) : la suppression
  se fait dans l'interface.

## Les playbooks de référence

Le dossier contient déjà 13 procédures publiques, gratuites et sourcées :

| Playbook | Catégorie d'incident | Source |
|---|---|---|
| IRM-07 Malware sous Windows | `virus` (logs antivirus FortiGate) | CERT Société Générale / CERT aDvens |
| IRM-05 Attaque réseau | `ips` (prévention d'intrusion) | idem |
| IRM-04 Déni de service distribué | `anomaly` (anti-DoS) | idem |
| IRM-11 Fuite de données | `dlp` | idem |
| ATT&CK T1110 Force brute (VPN, administration) | `vpn` | MITRE ATT&CK + NIST SP 800-61 |
| IRM-01 ver, IRM-02 intrusion Windows, IRM-03 intrusion Linux, IRM-06 défacement, IRM-16 phishing, IRM-17 rançongiciel, IRM-18 compromission large, IRM-22 compromission de messagerie | à choisir à la création de l'incident | CERT Société Générale / CERT aDvens |

- Les fiches **IRM** sont les méthodologies de réponse à incident du CERT Société Générale, traduites en français par
  le CERT aDvens (licence libre CC BY 3.0). Chaque fiche suit les phases : préparation, identification, confinement,
  remédiation, récupération, capitalisation. Le texte n'est pas réécrit.
- Le playbook **force brute** est traduit de MITRE ATT&CK (la référence mondiale des techniques d'attaque). Les
  quelques remarques propres à l'application y sont marquées « Note de l'application ».
- Chaque playbook indique sa **source** exacte (lien, version, licence).
- Une catégorie (`virus`, `vpn`…) fait proposer automatiquement le playbook aux nouveaux incidents de ce type.
- Régénérer les fiches (script) garde les identifiants : le suivi des incidents est préservé.

Ces procédures sont générales : à relire et adapter à l'organisation (contacts, outils) avant usage réel.
