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
- les pages appellent directement les `service.py` publics des fonctionnalités (pas d'appel HTTP interne).

## Routes des pages

| Page | GET | POST (formulaires) |
|---|---|---|
| Tableau de bord | `/` | — |
| Incidents | `/incidents?vue=en_cours\|traites&recherche=&criticite=&statut=&offset=` | `/incidents` (création depuis une alerte) |
| Fiche incident | `/incidents/{id}` | `/incidents/{id}/statut`, `/criticite`, `/assignation`, `/titre-categorie`, `/faux-positif`, `/playbook`, `/playbook/etapes/{etape_id}` |
| Alertes | `/alertes?criticite=&offset=` | — (bouton « Créer l'incident » → `POST /incidents`) |
| Journaux | `/journaux?statut=&offset=` (historique des imports) | — |
| Paramètres | `/parametres` → `/parametres/reponse-incidents` | `/parametres/reponse-incidents/delais/{criticite}`, `/parametres/reponse-incidents/escalade` |
| Playbooks | `/parametres/playbooks`, `/nouveau`, `/{id}/modifier` | `/nouveau`, `/{id}/modifier`, `/{id}/supprimer` |
| Journal d'audit | `/parametres/journal-audit?type_evenement=&offset=` | — |
| Clients, Utilisateurs | `/parametres/clients`, `/parametres/utilisateurs` (sections prévues, non prioritaires) | — |

Colonnes de la liste des incidents (demande de l'équipe) : référence, sévérité, titre/catégorie, statut + ouvert/traité,
alertes, plan (étapes réalisées / total), délai (dépassé, respecté, date limite), responsable, mis à jour. Un clic sur
une ligne ouvre la fiche, dont le premier panneau est le **playbook** de l'incident (étapes à cocher).

## Fonctionnement sans JavaScript

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

## Erreurs

`web_interface_registration.py` remplace les gestionnaires d'erreurs : chemins sous `/api` (et `/static`) ⇒ JSON
habituel ; pages ⇒ `templates/pages/error.html` (404, 409, 422). La page d'erreur n'interroge pas la base.

## Sécurité

- Échappement HTML automatique de Jinja2 : titres, logs, descriptions sont toujours affichés comme du texte.
- Pas de JavaScript métier ni de nouvelle dépendance externe ; Google Fonts reste utilisé comme dans la maquette.
  Le seul script du dashboard gère son apparence locale, sans requête réseau ni écriture métier.
- **Aucune authentification** pour l'instant (comme l'API) : ne pas exposer hors d'un poste de développement.
- Pas de jeton anti-CSRF : sans authentification ni cookie de session, il n'y a pas de session à détourner. **À
  ajouter avec l'authentification** (sinon un site tiers pourrait déclencher des actions au nom d'un analyste connecté).

## Affichage

- Dates stockées en UTC, affichées en `Europe/Paris` (`display_formatting.DISPLAY_TIMEZONE`, repli UTC si la base
  des fuseaux manque ; `tzdata` est dans `requirements.txt` pour l'image Docker).
- Libellés : `haute` s'affiche « Haute » (la maquette disait « Élevée ») pour rester aligné sur la base.

### Dashboard noir / blanc

La refonte est limitée à `/` : indicateurs plus lisibles, accès aux listes depuis les cartes, graphique conservé,
répartition par sévérité et liste d'incidents réels. Aucun chiffre, tendance ou statut de connexion n'est inventé.
Les trois modes de source (démo, écoute active, écoute inactive) et leurs avertissements sont conservés.

- `templates/pages/dashboard.html` remplit les blocs `document_attributes` et `page_head_scripts` du layout commun.
  Les autres pages ne chargent ni le script ni les couleurs de la refonte.
- `static/css/dashboard_theme.css` définit les jetons noir/blanc et les adaptations du menu, de la barre supérieure
  et des composants partagés **uniquement sur le dashboard**, avec `[data-dashboard-theme]`.
- `static/css/dashboard.css` porte la composition responsive propre au dashboard : quatre cartes (deux sur petit
  écran), graphique et sévérités en deux colonnes puis une, tableau dans un conteneur à défilement horizontal.
- `static/js/dashboard_theme.js` est chargé dans le `<head>` avant le CSS pour appliquer la préférence avant
  l'affichage. Il lit `localStorage["soc-dashboard-theme"]` (`light` ou `dark` uniquement), sinon le thème système.
  Le choix s'effectue avec deux boutons natifs (`aria-pressed`), accessibles au clavier, et reste local au navigateur.
  La couleur du navigateur (`theme-color`) suit le choix. Aucun cookie ni accès à la DB.
- Stockage interdit : avertissement visible et diagnostic dans la console ; le choix reste utilisable sur la page,
  mais n'est pas mémorisé. Sans JavaScript : thème noir, contrôles masqués, toutes les actions métier fonctionnent.

Validation : `python -m pytest tests/web_interface tests/features/dashboard`. Les tests couvrent les ressources,
le périmètre du thème, les liens et données réels, ainsi que les indicateurs de source. La mémorisation, les clics,
le clavier et la mise en page mobile doivent aussi être vérifiés dans un navigateur.

Vérification navigateur de cette refonte : thèmes noir/blanc à 320, 390, 768, 1024 et 1440 px sans débordement
horizontal de la page ; tableau défilable sur mobile ; choix conservé après rechargement ; activation au clavier ;
stockage local interdit avec avertissement visible ; script indisponible avec repli noir fonctionnel. La base de
prévisualisation était isolée et synthétique, sans accès aux logs réels.

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

`tests/web_interface/test_web_pages.py` : chaque page s'affiche sur une base vide, parcours complets via les
formulaires (création, actions, étapes, playbook, délais, escalade), erreurs HTML vs JSON, messages limités aux clés
connues. Vérification visuelle dans un navigateur : non automatisée.
