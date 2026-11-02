# L'interface des analystes — vue d'ensemble

## À quoi elle sert

C'est l'écran de travail de l'équipe SOC : voir les alertes, ouvrir et suivre les incidents, suivre les procédures
(playbooks) et régler l'application. Elle s'ouvre dans un navigateur à l'adresse du backend
(`http://localhost:8000` en développement).

Son apparence utilise un thème sauge clair et reposant, avec des couleurs de sévérité distinctes pour rester facile à lire. Elle est fabriquée en Python
par le serveur : il n'y a pas de programme séparé à installer ou à lancer, et aucun outil externe comme
OpenSearch Dashboards n'est nécessaire pour traiter les incidents.

## Les écrans

| Écran | Ce qu'on y fait |
|---|---|
| **Tableau de bord** | Voir d'un coup d'œil : incidents ouverts (et en retard), alertes à traiter, temps moyen de traitement, activité des 7 derniers jours, répartition par sévérité. Les cartes ouvrent directement la bonne liste : alertes, incidents en cours ou incidents traités. |
| **Incidents** | Deux onglets : **En cours** et **Traités**. Pour chaque incident : référence, sévérité, titre, catégorie, statut, alertes, avancement du plan, délai (respecté ou dépassé), responsable, dernière mise à jour. Recherche et filtres. |
| **Fiche d'un incident** | Un clic sur un incident ouvre **son playbook** et une checklist de réponse de sept points, cochable et mémorisée pour cet incident. À côté : les informations, les actions (statut, sévérité, responsable, faux positif…) et l'historique. La checklist est un aide-mémoire à adapter aux procédures internes. |
| **Alertes** | Un graphique en barres et un diagramme circulaire montrent les alertes critiques, moyennes et faibles. La liste présente le niveau de chaque alerte ; un bouton crée l'incident correspondant. Les niveaux « haute » sont regroupés avec les critiques, et les niveaux « information » avec les faibles, sans changer leur niveau source. |
| **Journaux** | L'historique des imports depuis FortiAnalyzer : réussis, échoués, combien d'alertes. |
| **Paramètres** | Clients (prévu), **Réponse aux incidents** (délais, escalade, playbooks), Utilisateurs (prévu), **Journal d'audit**. |

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
