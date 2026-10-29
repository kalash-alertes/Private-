# Paramètres, playbooks, délais et journal d'audit — vue d'ensemble

## Réponse aux incidents

### Délais de traitement

Pour chaque niveau de sévérité (critique, haute, moyenne, faible, information), l'équipe fixe le temps dont elle
dispose pour traiter un incident. Exemple : un incident critique doit être traité en 1 heure.

- La **date limite** d'un incident = son heure de création + le délai de sa sévérité.
- Si on change la sévérité d'un incident, sa date limite change aussi.
- Les valeurs de départ sont indicatives : **l'équipe doit les ajuster** à ses engagements.

### Escalade automatique

Pour chaque sévérité, on peut activer l'escalade : si un incident est toujours ouvert après sa date limite,
l'application le marque « escaladé » et, si une personne est indiquée, le lui réattribue. Cela n'arrive qu'une fois par
incident, c'est noté dans le journal d'audit, et **rien n'est exécuté sur l'infrastructure**. La vérification se fait
automatiquement toutes les 5 minutes, ou à la demande avec le bouton « Lancer l'escalade maintenant ».

### Playbooks

Un playbook est une procédure : un **nom**, une **liste d'étapes** dans l'ordre, et une **source** obligatoire (la
documentation ou la procédure interne validée d'où il vient — l'application ne présente jamais une procédure sans
référence).

- On peut lui associer une **catégorie** d'incident (par exemple « intrusion ») : chaque nouvel incident de cette
  catégorie reçoit automatiquement ce playbook.
- Dans la fiche d'un incident, l'analyste coche les étapes réalisées ; la liste des incidents montre l'avancement
  (« 2/4 »).
- Modifier un playbook garde les cases déjà cochées pour les étapes conservées.

## Journal d'audit

La liste de tout ce qui s'est passé : incident créé ou modifié, étape cochée, escalade, playbook créé, paramètre
changé. On ne peut ni modifier ni effacer un événement. Les **connexions réussies et échouées** y apparaîtront quand
la connexion des utilisateurs sera en place.

## Clients et Utilisateurs

Ces deux sections existent dans le menu mais sont vides pour l'instant : l'équipe les a jugées non prioritaires.
