# `web_interface` — interface des analystes

**Rôle** : les écrans de l'application, rendus **en Python** côté serveur (FastAPI + gabarits Jinja2), sans React ni
JavaScript métier. Toutes les pages partagent un thème sauge clair, une typographie lisible et des contrôles
adaptés au clavier et au mobile. Servie à la racine du backend
(`http://localhost:8000/`) ; l'API JSON reste sous `/api`.

## Organisation

| Dossier / fichier | Contenu |
|---|---|
| `pages/` | **un fichier Python par page** : routes HTTP + préparation des données (appelle les `service.py` publics) |
| `templates/layouts/` | mise en page commune (menu latéral, barre du haut) |
| `templates/partials/` | morceaux réutilisés : menu, barre du haut, onglets des Paramètres, macros (pastilles, pagination) |
| `templates/pages/` | **un gabarit HTML par page** |
| `static/css/` | styles par zone ; `foundation` définit les jetons et la police, `pink_theme` harmonise toutes les pages en dernier |
| `application_layout.py` | menu (groupes, liens, compteurs) et contexte commun |
| `template_rendering.py` | configuration Jinja2 + filtres d'affichage |
| `display_formatting.py` | libellés français, classes des pastilles, dates (Europe/Paris), durées |
| `icons.py` / `icon_shapes.py` | icônes SVG (lucide) ; `icon_shapes.py` est généré depuis la maquette |
| `activity_chart_svg.py` | graphique d'activité du tableau de bord en SVG |
| `alert_charts_svg.py` | graphiques Alertes (barres et cercle), générés côté serveur |
| `form_values.py`, `page_notices.py` | lecture des formulaires, messages de confirmation |
| `web_interface_registration.py` | branchement sur l'application, pages d'erreur HTML |

## Pages

`/` tableau de bord · `/incidents` (onglets En cours / Traités) · `/incidents/{id}` (playbook de l'incident + actions)
· `/alertes` · `/alertes/{source_log_id}` (champs originaux conservés, en lecture seule) · `/logs-bruts` (flux en direct)
· `/journaux` (imports) · `/parametres/reponse-incidents` · `/parametres/playbooks` ·
`/parametres/journal-audit` · `/parametres/clients` et `/parametres/utilisateurs` (prévus).

## Principes

- Les parcours métier restent sans JavaScript : formulaires HTML (POST → redirection → GET), fenêtres via
  `:target`, menu mobile via une case à cocher. JavaScript sert au flux Logs bruts et au choix local clair/sombre ;
  sans lui, le flux reste consultable avec un rechargement manuel et le thème reste clair.
- Aucune règle métier dans les pages : elles appellent les services du backend, qui valident et tracent tout.
- Ajouter une page : un fichier dans `pages/`, un gabarit dans `templates/pages/`, l'ajouter à `PAGE_ROUTERS`
  (`web_interface_registration.py`), et au menu si besoin (`application_layout.py`).
- Les cartes d'indicateurs du tableau de bord ouvrent la vue correspondante (incidents ouverts, alertes, incidents traités).
- La fiche d'incident présente le playbook et un aide-mémoire de réponse cochable, enregistré par incident.
- La page Alertes regroupe les niveaux en trois catégories d'affichage : « critique » rassemble critique et haute,
  « moyenne » conserve le niveau moyen, et « faible » rassemble faible et information. Les niveaux source restent
  inchangés et sont indiqués lorsqu'ils sont regroupés.
- Chaque alerte ouvre sa copie originale conservée via `pages/alerts_page.py` et `templates/pages/alert_source_log.html`.
  Les données manquantes sont signalées, et le texte syslog exact n'est pas reconstruit.
- Logs bruts : `static/js/raw_syslog_feed.js` conserve la ligne visible après insertion et retrait des messages ;
  `static/css/raw_syslog_feed.css` désactive l'ancrage natif pour éviter une double compensation. Les filtres restent
  actifs en direct et Pause ignore les réponses encore en cours.
- Le thème sauge/verre est global (`static/css/pink_theme.css`) ; les graphiques des pages restent rendus en SVG côté serveur.
- Le texte courant et les descriptions sont à 15 px, les tableaux à 14 px et les champs à 14 px ; les boutons font
  au moins 36 px de haut. Les couleurs de criticité et l'ancrage du flux restent inchangés. Les pages d'erreur
  chargent aussi le thème global, sans dépendre de la base.

**Voir l'interface remplie** (base de développement) : `python -m scripts.load_synthetic_demo_data` (données synthétiques).

**Tester** : `python -m pytest tests/web_interface`.
Les régressions navigateur utilisent Playwright avec Chromium et du HTTP simulé (aucun vrai appel FortiAnalyzer).
Si seul Chrome est installé : `$env:PLAYWRIGHT_BROWSER_CHANNEL = "chrome"` avant la commande.
Sans Playwright ou moteur disponible, ces seuls tests sont ignorés.
`test_application_theme_browser.py` vérifie toutes les pages avec des données synthétiques à 320, 390 et 1440 px :
absence de débordement global, lisibilité, boutons, contrastes, navigation mobile, photographie JPEG et repli opaque.

## Changer la photographie de fond

Remplacer **`static/images/application_background.jpg`** par sa propre photographie JPEG, en conservant ce nom.
Conseil : au moins 1920 px de large, cadrage paysage, fichier compressé. Faire **Ctrl+F5** après remplacement.
Le navigateur charge ce fichier local, jamais une photographie distante ; aucun élément de l'interface n'est ajouté
ni retiré. Le voile clair et les panneaux floutés préservent la lisibilité ; sans prise en charge du flou,
les panneaux restent opaques.
La sidebar reprend le rendu de la référence : photographie derrière un voile sombre, textes et icônes clairs,
entrée active verte. Ses liens, compteurs et indicateurs restent les mêmes ; elle utilise la même image remplaçable.
Son contour translucide fait 4 px, sans élargir le menu. Le bouton clair/sombre est inclus dans `templates/partials/application_theme_toggle.html`,
le choix mémorisé par `static/js/application_theme.js` et la variante sombre dans `static/css/dark_theme.css`.
Le script applique le choix avant le rendu et n'écrit aucune donnée métier ; si le stockage est bloqué,
il le signale et le bouton reste fonctionnel dans la page.

Photo livrée : forêt, [Unsplash](https://images.unsplash.com/photo-1441974231531-c6227db76b6e),
[licence Unsplash](https://unsplash.com/license) (téléchargement, usage et redistribution autorisés, y compris commercial).

**Doc** : [docs/technical/web_interface.md](../docs/technical/web_interface.md).
