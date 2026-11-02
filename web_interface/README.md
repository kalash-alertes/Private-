# `web_interface` — interface des analystes

**Rôle** : les écrans de l'application, rendus **en Python** côté serveur (FastAPI + gabarits Jinja2), sans React ni
JavaScript métier. Le dashboard propose désormais une apparence noire ou blanche ; un petit script local mémorise
uniquement ce choix dans le navigateur. Les autres pages gardent le thème existant. Servie à la racine du backend
(`http://localhost:8000/`) ; l'API JSON reste sous `/api`.

## Organisation

| Dossier / fichier | Contenu |
|---|---|
| `pages/` | **un fichier Python par page** : routes HTTP + préparation des données (appelle les `service.py` publics) |
| `templates/layouts/` | mise en page commune (menu latéral, barre du haut) |
| `templates/partials/` | morceaux réutilisés : menu, barre du haut, onglets des Paramètres, macros (pastilles, pagination) |
| `templates/pages/` | **un gabarit HTML par page** |
| `static/css/` | un fichier CSS par zone : `foundation`, `application_shell`, `components`, puis un par page |
| `static/css/dashboard_theme.css`, `static/js/dashboard_theme.js` | couleurs noir/blanc du dashboard et préférence locale (sans appel API) |
| `application_layout.py` | menu (groupes, liens, compteurs) et contexte commun |
| `template_rendering.py` | configuration Jinja2 + filtres d'affichage |
| `display_formatting.py` | libellés français, classes des pastilles, dates (Europe/Paris), durées |
| `icons.py` / `icon_shapes.py` | icônes SVG (lucide) ; `icon_shapes.py` est généré depuis la maquette |
| `activity_chart_svg.py` | graphique du tableau de bord en SVG |
| `form_values.py`, `page_notices.py` | lecture des formulaires, messages de confirmation |
| `web_interface_registration.py` | branchement sur l'application, pages d'erreur HTML |

## Pages

`/` tableau de bord · `/incidents` (onglets En cours / Traités) · `/incidents/{id}` (playbook de l'incident + actions)
· `/alertes` · `/journaux` (imports) · `/parametres/reponse-incidents` · `/parametres/playbooks` ·
`/parametres/journal-audit` · `/parametres/clients` et `/parametres/utilisateurs` (prévus).

## Principes

- Les parcours métier restent sans JavaScript : formulaires HTML (POST → redirection → GET), fenêtres via
  `:target`, menu mobile via une case à cocher. Seul le sélecteur noir/blanc du dashboard utilise JavaScript ;
  sans lui, le dashboard reste fonctionnel en noir et les boutons de thème sont masqués.
- Aucune règle métier dans les pages : elles appellent les services du backend, qui valident et tracent tout.
- Ajouter une page : un fichier dans `pages/`, un gabarit dans `templates/pages/`, l'ajouter à `PAGE_ROUTERS`
  (`web_interface_registration.py`), et au menu si besoin (`application_layout.py`).

**Voir l'interface remplie** (base de développement) : `python -m scripts.load_synthetic_demo_data` (données synthétiques).

**Tester** : `python -m pytest tests/web_interface`.

**Doc** : [docs/technical/web_interface.md](../docs/technical/web_interface.md).
