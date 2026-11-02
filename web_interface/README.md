# `web_interface` — interface des analystes

**Rôle** : les écrans de l'application, rendus **en Python** côté serveur (FastAPI + gabarits Jinja2), sans React ni
JavaScript. Le visuel reprend la maquette de l'équipe (`dashboard/` sur `main`). Servie à la racine du backend
(`http://localhost:8000/`) ; l'API JSON reste sous `/api`.

## Organisation

| Dossier / fichier | Contenu |
|---|---|
| `pages/` | **un fichier Python par page** : routes HTTP + préparation des données (appelle les `service.py` publics) |
| `templates/layouts/` | mise en page commune (menu latéral, barre du haut) |
| `templates/partials/` | morceaux réutilisés : menu, barre du haut, onglets des Paramètres, macros (pastilles, pagination) |
| `templates/pages/` | **un gabarit HTML par page** |
| `static/css/` | un fichier CSS par zone : `foundation`, `application_shell`, `components`, puis un par page |
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
· `/alertes` · `/journaux` (imports) · `/parametres/reponse-incidents` · `/parametres/playbooks` ·
`/parametres/journal-audit` · `/parametres/clients` et `/parametres/utilisateurs` (prévus).

## Principes

- Sans JavaScript : formulaires HTML (POST → redirection → GET), fenêtres via le sélecteur CSS `:target`, menu mobile
  via une case à cocher.
- Aucune règle métier dans les pages : elles appellent les services du backend, qui valident et tracent tout.
- Ajouter une page : un fichier dans `pages/`, un gabarit dans `templates/pages/`, l'ajouter à `PAGE_ROUTERS`
  (`web_interface_registration.py`), et au menu si besoin (`application_layout.py`).
- Les cartes d'indicateurs du tableau de bord ouvrent la vue correspondante (incidents ouverts, alertes, incidents traités).
- La fiche d'incident présente le playbook et un aide-mémoire de réponse cochable, enregistré par incident.
- La page Alertes regroupe les niveaux en trois catégories d'affichage : « critique » rassemble critique et haute,
  « moyenne » conserve le niveau moyen, et « faible » rassemble faible et information. Les niveaux source restent
  inchangés et sont indiqués lorsqu'ils sont regroupés.
- Le thème sauge clair est global (`static/css/pink_theme.css`) ; les graphiques des pages sont rendus en SVG côté serveur.

**Voir l'interface remplie** (base de développement) : `python -m scripts.load_synthetic_demo_data` (données synthétiques).

**Tester** : `python -m pytest tests/web_interface`.

**Doc** : [docs/technical/web_interface.md](../docs/technical/web_interface.md).
