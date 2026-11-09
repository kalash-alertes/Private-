# Interface web (`web_interface/`)

## Décision

L'interface des analystes n'est **pas** OpenSearch Dashboards ni un frontend React séparé : elle est rendue **en
Python** par le backend (FastAPI + Jinja2), sans JavaScript métier. Le visuel initial reprend la maquette React de l'équipe
(`dashboard/` sur la branche `main`, thème sombre « FAnalyzer IR ») : couleurs, typographie (DM Sans / Manrope),
menu latéral, cartes, pastilles et tableaux. Le CSS de la maquette a été découpé dans `static/css/`, les icônes
lucide extraites de son build (`icon_shapes.py`, généré), le graphique recharts remplacé par un SVG produit en Python
(`activity_chart_svg.py`).

Conséquences :
- un seul service à déployer (le backend sert pages, CSS et API) ; pas de CORS pour l'interface ;
- l'API JSON est déplacée sous **`/api`** (la racine est aux pages) ; elle reste utilisable par un autre client ;
- Les pages appellent directement les `service.py` publics des fonctionnalités (pas d'appel HTTP interne). Le thème
global est sauge clair ; les graphiques de synthèse sont des SVG produits en Python, sans JavaScript.

## Routes des pages

| Page | GET | POST (formulaires) |
|---|---|---|
| Tableau de bord | `/` | — ; les cartes ouvrent Alertes, Incidents ouverts ou Incidents traités |
| Incidents | `/incidents?vue=en_cours\|traites&recherche=&criticite=&statut=&offset=` | `/incidents` (création depuis une alerte) |
| Fiche incident | `/incidents/{id}` | `/incidents/{id}/statut`, `/criticite`, `/assignation`, `/titre-categorie`, `/faux-positif`, `/playbook`, `/playbook/etapes/{etape_id}`, `/checklist/{item_id}` |
| Alertes | `/alertes?criticite=&groupe=&offset=` | — (bouton « Créer l'incident » → `POST /incidents`) ; rubriques dépliables par type, indicateurs par sévérité et graphiques |
| Log original d'une alerte | `/alertes/{source_log_id}` | — ; copie des champs conservés et lien vers l'incident éventuel |
| Journaux | `/journaux?statut=&offset=` (historique des imports, pertes système UDP) | — |
| Logs bruts | `/logs-bruts?criticite=&enregistrement=&recherche=` ; fragment `/logs-bruts/nouveaux?apres=N` | — (voir [raw_syslog_feed.md](raw_syslog_feed.md)) |
| Paramètres | `/parametres` → `/parametres/reponse-incidents` | `/parametres/reponse-incidents/delais/{criticite}`, `/parametres/reponse-incidents/escalade` |
| Playbooks | `/parametres/playbooks`, `/nouveau`, `/{id}/modifier` | `/nouveau`, `/{id}/modifier`, `/{id}/supprimer`, `/synchroniser` (relit les fichiers JSON) |
| Journal d'audit | `/parametres/journal-audit?type_evenement=&offset=` | — |
| Clients, Utilisateurs | `/parametres/clients`, `/parametres/utilisateurs` (sections prévues, non prioritaires) | — |

Colonnes de la liste des incidents (demande de l'équipe) : référence, sévérité, titre/catégorie, statut + ouvert/traité,
alertes, plan (étapes réalisées / total), délai (dépassé, respecté, date limite), responsable, mis à jour. Un clic sur
une ligne ouvre la fiche, dont le premier panneau est le **playbook** de l'incident (étapes à cocher).

## Fonctionnement sans JavaScript

`static/js/raw_syslog_feed.js` (page Logs bruts) ajoute les nouveaux logs toutes les 3 s à partir
d'un fragment HTML rendu par Jinja2 ; sans lui, la page fonctionne avec un rechargement manuel.
`static/js/application_theme.js` gère uniquement l'apparence clair/sombre ; sans lui, le thème clair reste utilisable
et son bouton est masqué.

- **POST → redirection 303 → GET** : succès ⇒ redirection avec `?notice=<clé>` ; seules les clés de
  `page_notices.py` sont affichées (aucun texte de l'URL n'est recopié dans la page).
- **Refus** (règle métier ou validation) : la page est réaffichée avec le motif, code 422, sans rien modifier
  (`form_values.describe_action_error` ; les valeurs saisies ne sont pas recopiées dans le message).
- **Fenêtres** (« Nouvel incident », confirmation de suppression) : sélecteur CSS `:target` (`#nouvel-incident`).
- **Menu mobile** : case à cocher `#sidebar-toggle` + `label`.
- **Formulaire de playbook** : « Ajouter une étape » / « Supprimer » sont des boutons d'envoi `action=...` ; le
  serveur réaffiche le formulaire modifié sans enregistrer. Un bouton « Enregistrer » caché est placé en premier pour
  que la touche Entrée enregistre. Chaque étape garde son `id` caché (préserve son suivi dans les incidents).
- **Lignes cliquables** : le lien du titre s'étend sur toute la ligne (`::after`).
- **Cartes du tableau de bord** : incidents ouverts → `/incidents?vue=en_cours`, alertes à traiter → `/alertes`,
  incidents traités et temps moyen → `/incidents?vue=traites`.
- **Checklist de réponse** : chaque incident reçoit sept tâches suggérées, indépendantes du playbook et stockées dans
  `incident_response_checklist`. Une case est enregistrée par formulaire POST ; les changements effectifs sont datés,
  audités et bloqués après clôture. C'est un aide-mémoire générique, à adapter aux règles internes, et non une procédure
  officielle.

## Erreurs

`web_interface_registration.py` remplace les gestionnaires d'erreurs : chemins sous `/api` (et `/static`) ⇒ JSON
habituel ; pages ⇒ `templates/pages/error.html` (404, 409, 422). La page d'erreur n'interroge pas la base.

## Sécurité

- Échappement HTML automatique de Jinja2 : titres, logs, descriptions sont toujours affichés comme du texte.
- Pas de JavaScript métier ni de nouvelle dépendance externe ; Google Fonts reste utilisé comme dans la maquette.
  Le script du thème gère l'apparence locale, sans requête réseau ni écriture métier.
- **Aucune authentification** pour l'instant (comme l'API) : ne pas exposer hors d'un poste de développement.
- Pas de jeton anti-CSRF : sans authentification ni cookie de session, il n'y a pas de session à détourner. **À
  ajouter avec l'authentification** (sinon un site tiers pourrait déclencher des actions au nom d'un analyste connecté).

## Affichage

- La liste Alertes présente une rubrique native HTML `details` / `summary` par valeur exacte de `logs.type`
  (par exemple `vpn`, `forward`), triée par effectif décroissant et repliée initialement. À effectifs égaux, le type
  exact départage alphabétiquement les rubriques. Le tri utilise tous les logs correspondant au filtre courant,
  pas seulement les 25 lignes affichées. Elle fonctionne au clavier et sans
  JavaScript. Ce regroupement est visuel : aucune création, fusion ou modification d'incident.
- `source_logs.count_source_logs_by_type` calcule les effectifs en SQL sur tous les logs conservés, après filtre
  de criticité. Les types ne sont pas déduits d'une seule page de 25 logs : même un type ancien reste accessible.
  Chaque rubrique charge au plus 25 métadonnées, triées par date d'événement puis UUID décroissants, avec les mêmes
  liens vers le log original et les incidents qu'avant. Les données brutes ne sont pas chargées dans la liste.
- `groupe` désigne le type exact (1 à 255 caractères) auquel appliquer `offset` ; les autres rubriques restent
  sur leur première page. Les liens conservent le type et la criticité, et la rubrique paginée est automatiquement
  ouverte après navigation. Un filtre soumis remet les pages à zéro. Les caractères des types sont échappés dans
  le HTML et encodés dans les URL. Un offset sans groupe ne déplace aucune rubrique.
  Les compteurs et graphiques globaux, la collecte et son seuil restent inchangés ; aucune migration nécessaire.
- Dates stockées en UTC, affichées en `Europe/Paris` (`display_formatting.DISPLAY_TIMEZONE`, repli UTC si la base
  des fuseaux manque ; `tzdata` est dans `requirements.txt` pour l'image Docker).
- Libellés : `haute` s'affiche « Haute » (la maquette disait « Élevée ») pour rester aligné sur la base.
- Sur la page Alertes, les sévérités sont regroupées sans modifier leur valeur source : **Critique** inclut `critique`
  et `haute`, **Moyenne** inclut `moyenne`, et **Faible** inclut `faible` et `information`. Les badges précisent le
  niveau source lorsqu'il est regroupé. Le total des groupes est calculé à partir des comptes filtrés par niveau.
- `alert_charts_svg.py` dessine le graphique en barres et l'anneau circulaire à partir de ces trois comptes. Les SVG
  portent un nom accessible ; la légende HTML expose les comptes même sans interprétation visuelle du graphique.
- Chaque alerte propose « Voir le log original ». `alerts_page.py` appelle le service public
  `source_logs.fetch_source_log_detail` avec son UUID ; `alert_source_log.html` affiche ses métadonnées et
  `donnees_brutes` en JSON indenté via `tojson` (caractères HTML échappés, structures imbriquées conservées).
  Il s'agit des champs reçus et stockés, pas d'une reconstruction du texte syslog exact, qui n'est pas conservé en
  base. `None` est signalé explicitement ; un dictionnaire vide reste affiché comme `{}`. Un UUID inconnu donne 404,
  un UUID invalide 422, via les pages d'erreur existantes. Aucun changement de schéma ni écriture en base.
- `static/css/pink_theme.css`, chargée en dernier dans le layout commun, applique les surfaces sauge pâle et les
  couleurs de texte à contraste élevé sur toutes les pages. Les indicateurs de criticité conservent leurs couleurs
  sémantiques.

### Thème commun et lisibilité

- `foundation.css` conserve DM Sans pour le texte, avec repli Segoe UI/sans-serif si la police distante est
  indisponible ; Manrope reste la police des titres. Aucun nouveau téléchargement ni dépendance.
- Les jetons communs `--accent`, `--surface-raised`, `--shadow-panel` et `--radius-panel` regroupent les accents
  sauge, surfaces, ombres discrètes et angles de cartes. `pink_theme.css` garde son nom historique et sa place en
  dernier : il harmonise les anciens styles de pages sans changer leur structure ou leurs règles métier.
- Texte courant/descriptions : 15 px ; tableaux/champs : 14 px ; détails des logs : 13 px et police monospace ;
  titres de panneaux : 16 px, titres de page : 26–34 px. Les badges restent compacts mais lisibles.
- Boutons : hauteur minimale 40 px (36 px pour les petits). Leurs icônes héritent de leur couleur ; le bouton
  primaire blanc sur sauge est vérifié à un contraste WCAG d'au moins 4,5:1. Les champs de recherche et de filtrage
  ont un focus visible sur leur conteneur, même si l'ancien champ interne désactive son contour.
- Le bandeau de surveillance reçoit une surface claire. Les alertes, erreurs et criticités conservent leurs
  couleurs sémantiques. `prefers-reduced-motion` supprime également les animations de pulsation et d'apparition.
- Mobile : barre supérieure sur deux lignes si nécessaire, recherche toujours disponible, contrôles et formulaires
  repliables, tableaux larges défilant dans leur conteneur. Les colonnes des logs restent alignées entre en-tête et
  lignes ; les champs longs se replient. `overflow-anchor: none` et l'algorithme de lecture stable restent inchangés.
- `pages/error.html` charge également le thème, mais reste autonome et sans requête en base.

### Photographie locale et effet verre

- Fond unique : `web_interface/static/images/application_background.jpg`, vraie photographie JPEG (1920 × 1279,
  environ 780 Kio), servie par la route statique existante. Source :
  [Unsplash](https://images.unsplash.com/photo-1441974231531-c6227db76b6e), sous
  [licence Unsplash](https://unsplash.com/license), autorisant usage et redistribution. Pas de SVG de fond,
  génération à l'exécution ni requête vers un fournisseur d'images depuis le navigateur.
- Remplacement : écraser ce fichier par une photo JPEG de même nom puis rechargement forcé ; si un autre format
  ou nom est souhaité, adapter uniquement l'URL dans `pink_theme.css`. `cover`, centrage et attachement fixe
  permettent le recadrage selon la fenêtre. Les caches navigateur nécessitent Ctrl+F5.
- Un voile clair fixe couvre la photo, y compris très sombre. Les surfaces ont un fond à environ 85 % d'opacité
  et `backdrop-filter: blur(18px)` (avec préfixe WebKit). Aucun changement des éléments HTML, des routes, des
  formulaires, de l'ordre des panneaux, de la collecte ou de l'ancrage des logs.
- Le bloc `@supports` applique la transparence uniquement quand le flou est disponible ; sinon les surfaces
  restent opaques. Une photo absente conserve la couleur de fond sauge. En-tête et pied de page reçoivent eux aussi
  une surface lisible. Les couleurs des criticités, états et boutons primaires sont conservées.
- Tests : décodage effectif du JPEG local, dimensions, verre sur toutes les pages, contraste du texte ≥ 4,5:1
  sur les surfaces principales même avec un arrière-plan noir, photo indisponible et repli sans filtre.
- Sidebar : même JPEG local, voile vert sombre à 80 %, flou de 3 px (photo plus visible que sous les panneaux),
  textes/icônes clairs, entrée active verte. Surcharges limitées à `.sidebar` pour préserver les autres pages.
  Sans flou, fond sombre opaque. Tests de contraste sur fond noir **et blanc**, et sur l'entrée active ; liens,
  compteurs et états de réception inchangés.

### Contour de sidebar et bouton clair/sombre

- Sidebar : contour blanc translucide de 2 px et léger reflet intérieur, sans modifier sa largeur extérieure ni les liens.
  Elle suit le choix du thème : voile sauge clair et textes foncés en clair, voile sombre et textes blancs en sombre.
  La photographie, l'entrée active verte et les indicateurs sont conservés dans les deux modes.
- `partials/application_theme_toggle.html` est inclus dans la barre supérieure et la page d'erreur. Bouton natif,
  utilisable au clavier, `aria-pressed` indique le mode sombre ; son libellé annonce le mode à activer.
- `application_theme.js` est chargé dans le `<head>` avant les styles : il lit `fAnalyzerInterfaceTheme` dans
  `localStorage` et applique `html[data-theme="light|dark"]` avant le rendu pour éviter un éclair clair sur un choix
  sombre. Par défaut : clair ; seules les valeurs `dark`/`light` sont reconnues. Le choix suit la navigation,
  le rechargement et les autres onglets de la même origine (`storage`).
- `dark_theme.css`, chargé après `pink_theme.css`, ajuste les surfaces, champs, textes et axes de graphiques.
  Photo, dimensions, défilement des logs et criticités sont conservés ; notices et badges gardent leurs couleurs.
  Les surfaces sombres restent opaques si le flou est indisponible.
- Stockage indisponible : avertissement explicite en console ; le bouton fonctionne dans la page courante et son
  titre signale si le choix n'a pas pu être mémorisé. Aucun accès aux données métier ni nouvelle dépendance.
- Tests : toutes les pages en clair **et sombre** à 320/390/1440 px, contrastes, clavier, navigation/rechargement,
  page d'erreur, stockage bloqué et bouton absent visuellement sans JavaScript.

### Dashboard

- `templates/pages/dashboard.html` : quatre cartes `<a class="stat-card stat-card-link">` (lien vers
  `/incidents?vue=en_cours`, `/alertes`, `/incidents?vue=traites`), graphique d'activité, répartition par sévérité,
  liste des incidents ouverts. Aucun chiffre, tendance ou statut de connexion n'est inventé.
- Le bandeau de contexte affiche `alert_source_indicator` (`.source-context.alert-source-<mode>`) : les trois modes
  de source (démo, écoute active, écoute inactive) restent visibles sur le dashboard comme sur les autres pages.
- `static/css/dashboard.css` porte la composition responsive ; les couleurs viennent de `pink_theme.css`
  (thème global). L'ancien thème noir/blanc propre au dashboard (`dashboard_theme.css`/`.js`, blocs
  `document_attributes` et `page_head_scripts` du layout) a été retiré lors de la fusion des branches
  `analyzer_connected` et `feature/fortianalyzer-collector` : il entrait en conflit avec le thème global
  (`pink_theme.css` force les couleurs avec `!important`).
- `pink_theme.css` contient aussi les versions claires de l'indicateur de source (bandeau démo, badge du haut,
  statut du menu), définies d'abord en sombre dans `application_shell.css`.

## Indicateur de source des alertes

`application_layout.build_alert_source_indicator()` (sans accès à la base, via
`log_collection.service.describe_collection_configuration`) fournit `alert_source_indicator` (`mode`, `badge_label`,
`description`) à toutes les pages. `mode` ∈ `demo` / `live` / `live-inactive` sert de classe CSS : `body.alert-source-page-<mode>`
(liseré fixe de 3 px), badge `.alert-source-badge` dans `partials/topbar.html`, ligne dans `partials/sidebar.html`, et
bandeau `.demo-mode-ribbon` (seulement en `demo`, `layouts/application_layout.html`). Styles :
`static/css/application_shell.css` ; animation du point vert désactivée si `prefers-reduced-motion`. La page d'erreur,
autonome, ne l'affiche pas.

## Données de démonstration

`python -m scripts.load_synthetic_demo_data` (base migrée, `APPLICATION_ENVIRONMENT` ≠ `production`) : 3 playbooks,
8 alertes, 6 incidents, un import. Tout est synthétique et marqué comme tel.

## Tests

`tests/web_interface/test_web_pages.py` : chaque page s'affiche sur une base vide, liens des cartes du tableau de bord,
parcours complets via les formulaires (création, actions, étapes, checklist, playbook, délais, escalade), erreurs HTML
vs JSON, messages limités aux clés connues.
`test_application_theme_browser.py` charge les réponses du client de test dans Chromium, sans réseau réel
(polices distantes bloquées, repli typographique testé). Il couvre les pages peuplées, formulaires et erreurs à
320/390/1440 px : débordement global ≤ 1 px, texte courant ≥ 15 px, boutons ≥ 36 px et ≥ 13 px,
contraste primaire ≥ 4,5:1, recherche et navigation mobiles conservées.
`test_raw_syslog_feed_browser.py` vérifie l'ancrage et la pause avec les feuilles de style réellement chargées.
Exécution : `$env:PLAYWRIGHT_BROWSER_CHANNEL = "chrome"; python -m pytest tests/web_interface` si Chrome est installé,
sinon Chromium Playwright. Sans Playwright ou moteur disponible, seuls les tests navigateur sont ignorés.
- Les rubriques Alertes ont un en-tête contrasté clair/sombre, un titre Manrope 18 px / 800, un accent latéral
  et une flèche encadrée. Les logs restent à 14 px / 500 et le tableau est en retrait de 18 px.
  Une marge de 14 px et un contour arrondi séparent les rubriques ; ces repères ne dépendent pas du texte.
  Les tests navigateur vérifient l'écart typographique, le fond distinct, le retrait et la séparation en clair/sombre.
- En mode réel, les trois compteurs de sévérité et les deux graphiques Alertes utilisent
  `raw_syslog_feed.read_raw_syslog_statistics`, avant filtrage, sur une période commune depuis le démarrage
  du récepteur. Ils ne dépendent pas des 2 000 messages conservés pour affichage. Faible inclut faible et information ;
  les niveaux inconnus sont signalés hors graphique. Les compteurs sont volatils et repartent à zéro au redémarrage,
  y compris lors du rechargement du backend. Une écoute inactive est explicitement signalée.
  Le total en base, les rubriques et les actions restent fondés sur les logs stockés. En mode démo,
  les graphiques gardent leurs comptes historiques en base. Aucun abaissement du seuil, aucune nouvelle écriture,
  aucune création automatique d'incident. Les faibles ne deviennent pas des alertes à traiter.
