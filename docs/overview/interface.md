# L'interface des analystes — vue d'ensemble

## À quoi elle sert

C'est l'écran de travail de l'équipe SOC : voir les alertes, ouvrir et suivre les incidents, suivre les procédures
(playbooks) et régler l'application. Elle s'ouvre dans un navigateur à l'adresse du backend
(`http://localhost:8000` en développement).

Son apparence utilise un thème sauge clair et reposant, avec des couleurs de sévérité distinctes pour rester facile à lire. Elle est fabriquée en Python
par le serveur : il n'y a pas de programme séparé à installer ou à lancer, et aucun outil externe comme
OpenSearch Dashboards n'est nécessaire pour traiter les incidents.

## Une présentation plus lisible

Toutes les pages partagent la même présentation : textes plus grands (encore agrandis légèrement pour faciliter
la lecture), titres mieux distincts, cartes aérées,
ombres discrètes et boutons plus confortables. Les logs gardent une police adaptée aux données techniques et leurs
couleurs de gravité restent reconnaissables.

Sur téléphone, les boutons se réorganisent, la recherche reste accessible et les grands tableaux défilent dans leur
cadre. Au clavier, le champ ou bouton sélectionné est entouré d'un contour visible. Si vous avez choisi de réduire
les animations dans votre appareil, les effets animés sont désactivés.

Cette refonte ne change ni la collecte, ni le filtrage, ni les chiffres des graphiques. Après une mise à jour,
un rechargement forcé du navigateur (**Ctrl+F5**) permet de charger le nouveau style.

### Un fond photographique et un effet verre

Une photographie de forêt apparaît derrière les menus, cartes et champs translucides. Ils gardent les mêmes
contenus, liens et actions ; un léger flou et un voile clair permettent de lire les textes.
Le menu latéral est plus sombre, avec la photo visible derrière, des textes blancs et un fond vert pour la rubrique
ouverte, comme dans la référence visuelle. Tous ses liens et compteurs sont conservés.
Un contour translucide plus épais souligne le menu. Le bouton **Mode sombre / Mode clair**, en haut de l'écran, change
l'apparence de toute l'application tout en conservant la photo. Votre choix est mémorisé sur ce navigateur et
reste actif quand vous changez de page. Sans JavaScript, l'interface reste en clair et ce bouton n'apparaît pas.

Pour personnaliser le fond, remplacez [application_background.jpg](../../web_interface/static/images/application_background.jpg)
par votre propre photo **JPEG**, en gardant le même nom, puis faites **Ctrl+F5**. Pas besoin de modifier le code.
Si votre navigateur ne sait pas afficher le flou, les cartes restent opaques et lisibles.

## Les écrans

| Écran | Ce qu'on y fait |
|---|---|
| **Tableau de bord** | Voir d'un coup d'œil : incidents ouverts (et en retard), alertes à traiter, temps moyen de traitement, activité des 7 derniers jours, répartition par sévérité. Les cartes ouvrent directement la bonne liste : alertes, incidents en cours ou incidents traités. |
| **Incidents** | Deux onglets : **En cours** et **Traités**. Pour chaque incident : référence, sévérité, titre, catégorie, statut, alertes, avancement du plan, délai (respecté ou dépassé), responsable, dernière mise à jour. Recherche et filtres. |
| **Fiche d'un incident** | Un clic sur un incident ouvre **son playbook** et une checklist de réponse de sept points, cochable et mémorisée pour cet incident. À côté : les informations, les actions (statut, sévérité, responsable, faux positif…) et l'historique. La checklist est un aide-mémoire à adapter aux procédures internes. |
| **Alertes** | Un graphique en barres et un diagramme circulaire montrent les alertes critiques, moyennes et faibles. Par défaut, seuls les logs de dangerosité moyenne, haute et critique sont collectés : la case Faible indique alors « Non collectées ». La liste présente le niveau de chaque alerte ; « Voir le log original » ouvre les champs conservés à la collecte, et un bouton crée l'incident correspondant. Les niveaux « haute » sont regroupés avec les critiques, et les niveaux « information » avec les faibles, sans changer leur niveau source. |
| **Journaux** | L'historique des imports depuis FortiAnalyzer : réussis, échoués, combien d'alertes. |
| **Logs bruts** | Tout ce que FortiAnalyzer envoie, en direct et avant le tri par dangerosité ; un clic déplie un log sur tous ses champs. Explique l'écart avec FortiAnalyzer ([détails](raw_logs_and_reference_playbooks.md)). |
| **Paramètres** | Clients (prévu), **Réponse aux incidents** (délais, escalade, playbooks), Utilisateurs (prévu), **Journal d'audit**. |

## Le tableau de bord

Le tableau de bord utilise le même thème sauge clair que les autres écrans. Chaque carte est cliquable et ouvre
la bonne liste : incidents ouverts, alertes à traiter ou incidents traités. Le graphique couvre les sept derniers
jours, et la liste du bas ouvre directement chaque incident. En haut à droite, un petit indicateur rappelle d'où
viennent les alertes (démonstration, FortiAnalyzer en direct, ou réception inactive) et mène à la page Journaux.

## Démonstration ou vraies alertes ?

Le haut de chaque page le dit, avec une couleur :

| Ce qu'on voit | Signification |
|---|---|
| Bandeau rayé **orange** « MODE DÉMONSTRATION », badge « MODE DÉMO » | Les alertes sont inventées (`APP_IS_IN_DEMO=true`). |
| Badge **vert** « EN DIRECT », point qui pulse | Vraies alertes : l'application écoute FortiAnalyzer. |
| Badge **rouge** « SYSLOG INACTIF » | Mode réel, mais l'écoute n'a pas démarré : aucune alerte ne peut arriver (motif dans Journaux). |

Un liseré de la même couleur borde le haut de la fenêtre, et le bas du menu rappelle la source. Un clic mène à Journaux.

## Ce que l'utilisateur en retire

- Il sait toujours quoi faire ensuite : le playbook de l'incident est la première chose affichée.
- Il voit tout de suite les incidents en retard.
- Chaque action est enregistrée dans le journal d'audit : on peut retrouver ce qui s'est passé.

## Ce qui manque encore

- La **connexion des utilisateurs** : pour l'instant, tout le monde arrive directement sur l'application, et le
  responsable d'un incident est un nom saisi librement. Ne pas ouvrir l'application en dehors d'un poste de
  développement.
- Les sections Paramètres > Clients et Utilisateurs (jugées non prioritaires).
- Les vraies alertes : elles arriveront quand le collecteur FortiAnalyzer sera branché. En attendant, des données de
  démonstration (inventées) peuvent être chargées pour voir les écrans remplis.
