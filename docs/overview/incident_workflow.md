# Traitement des alertes et incidents — vue d'ensemble

## Le parcours d'une alerte

1. **Import** : un programme (le « collecteur », à venir) récupère les alertes critiques de FortiAnalyzer.
   Chaque passage est noté dans l'**historique des imports** : quand, réussi ou non, combien d'alertes reçues,
   nouvelles, déjà connues. En cas d'échec, une explication est enregistrée (sans mot de passe ni jeton).
2. **Log** : chaque alerte n'est enregistrée **qu'une seule fois**, même si elle est revue plusieurs fois.
   Sa gravité d'origine (« criticité source ») est conservée telle quelle, pour toujours.
3. **Incident** : quand une alerte mérite un traitement, l'analyste ouvre un incident à partir d'elle
   (une alerte = un incident au maximum). L'incident démarre avec la même gravité que l'alerte.
4. **Traitement** : l'analyste peut
   - changer le **statut** (nouveau, en cours, en attente, résolu, clôturé) ;
   - **réévaluer la gravité** à la hausse ou à la baisse — la gravité d'origine reste visible à côté ;
   - déclarer un **faux positif**, toujours avec une justification écrite ;
   - **attribuer** l'incident à une personne (ou retirer l'attribution).
5. **Clôture** : la date de clôture est enregistrée automatiquement. Un incident clôturé ne peut plus être modifié ;
   pour le corriger, on le **rouvre** (la date de clôture est alors effacée).

## Ce qui n'est pas encore là

- La collecte réelle depuis FortiAnalyzer (en attente d'informations sur l'API).
- Les écrans (seule l'API existe).
- La connexion des utilisateurs : le responsable d'un incident est pour l'instant un simple nom saisi.
- L'historique des changements (qui a changé quoi, quand) : seules les valeurs actuelles sont conservées.
- Les procédures de réponse (playbooks), les notes d'investigation et les rapports.

## Règles encore provisoires

Les statuts, les niveaux de gravité, le fait que tout changement de statut soit permis et le blocage des incidents
clôturés sont des choix temporaires, à valider par l'équipe.
