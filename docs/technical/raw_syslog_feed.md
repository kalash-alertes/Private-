# Fonctionnalité `raw_syslog_feed` — logs bruts en direct

Code : `backend/features/raw_syslog_feed/` (aucune table), page `web_interface/pages/raw_syslog_feed_page.py`.

## Pourquoi

La base ne garde que les logs au-dessus de `LOG_COLLECTION_MINIMUM_CRITICALITY` (défaut `moyenne`). Comparée à la vue
de FortiAnalyzer, elle paraît donc presque vide : mesuré le 03/11/2026 sur le FortiGate de l'équipe, **≈ 98,8 % des
logs reçus sont en `level="notice"`** (trafic `forward`/`local`, IPsec « Progress »), donc classés `faible` et écartés.
Cette page montre ce qui arrive réellement, avant tout filtre, pour :
- vérifier qu'aucun log ne manque (compteurs de pertes) ;
- comprendre l'écart avec FortiAnalyzer (répartition par niveau, « enregistré » / « écarté ») ;
- lire un log complet (tous ses champs, texte d'origine), comme le « Discover » de Wazuh.

## Données

- **Mémoire d'affichage** du récepteur syslog (`FortiAnalyzerSyslogReceiver._recent_messages`) : `deque` bornée à
  `SYSLOG_RECENT_MESSAGES_KEPT_FOR_DISPLAY` (défaut 2 000). Elle reçoit **tous** les messages des émetteurs acceptés,
  lisibles ou non, avec un numéro croissant (`sequence_number`). Elle est distincte de la file de collecte : la lire ne
  retire rien (`read_recent_messages(after_sequence_number)`). Rien n'est écrit en base. À ~30 logs/s, 2 000 messages
  ≈ 1 minute d'historique.
- **Compteur par niveau** : `accepted_message_count_by_severity_label` (valeur brute de `severity`, sinon `level`,
  `(aucun)` si absent), depuis le démarrage de l'écoute.
- **Pertes système UDP** : `RcvbufErrors` de `/proc/net/snmp` (réseau du conteneur), en différence avec la valeur lue au
  démarrage de l'écoute (`count_udp_datagrams_lost_by_system_since_start`). Ce sont des datagrammes jetés par le noyau
  AVANT l'application ; aucun autre compteur ne les voit. `None` hors Linux.

Le devenir d'un log (criticité, enregistré ou non, motif) est calculé par
`log_collection.service.evaluate_raw_log_against_collection_threshold` : mêmes règles que la collecte, l'affichage ne
peut pas diverger.

## API

`GET /api/logs-bruts?criticite=&enregistrement=tous|enregistres|ecartes&recherche=&apres=&limite=` →
`RawSyslogFeedRead` : `messages` (plus récent d'abord, au plus `limite` ≤ 500), `dernier_numero` (à renvoyer dans
`apres` pour ne recevoir que les nouveaux), `statistiques` (reçus, enregistrables, écartés par le seuil, illisibles,
refusés, perdus file pleine, perdus par le système, répartition par niveau). `recherche` : sous-chaîne sans casse dans le
texte brut. En démonstration : liste vide.

## Page `/logs-bruts`

- Bilan « Reçus contre enregistrés » + tableau par niveau d'origine (part, criticité dans l'application, devenir).
- Flux : un `<details>` par log ; la ligne résumée (heure à la seconde, criticité, niveau d'origine, équipement, type,
  `logdesc`/`msg`/`action`, devenir) se déplie sur la table des champs et le texte reçu (`partials/raw_syslog_feed_entries.html`).
- Filtres : criticité, devenir, recherche texte (formulaire GET classique).
- Direct : `static/js/raw_syslog_feed.js` appelle `/logs-bruts/nouveaux?apres=N&<filtres>` toutes les 3 s. Ce fragment
  (`partials/raw_syslog_feed_update.html`) contient deux `<template>` (nouvelles lignes, bilan) rendus par Jinja2 : le
  script ne fabrique aucun HTML à partir des logs (texte échappé côté serveur). Pause/Reprendre ; pas d'appel quand
  l'onglet est caché. Si l'analyste a déplié une ligne ou fait défiler la liste, la position est conservée (hauteur
  ajoutée compensée). Au plus 500 lignes dans la page ; les lignes dépliées ne sont jamais retirées.
- Sans JavaScript : la page reste lisible, rechargement manuel.

## Cas limites

- Le backend redémarre (y compris `--reload` en développement) : mémoire et compteurs repartent de zéro.
- Messages d'un émetteur refusé (`SYSLOG_ALLOWED_SENDER_ADDRESSES`) : comptés, non gardés pour l'affichage.
- Le filtre `criticite` s'applique après la recherche texte ; un message illisible n'a pas de criticité.

## Tests

`tests/features/raw_syslog_feed/`, `tests/integrations/fortianalyzer/test_fortianalyzer_syslog_receiver.py`
(mémoire bornée, compteur par niveau, lecture de `/proc/net/snmp` sur un fichier de test),
`tests/web_interface/test_web_pages.py` (page, fragment, échappement).
