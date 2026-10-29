# Vue d'ensemble du projet

## À quoi ça sert ?

FortiAnalyzer détecte des alertes de sécurité. Cette application aide l'équipe à **les traiter** : retrouver une alerte, ouvrir un incident,
l'attribuer à quelqu'un, juger sa gravité, écarter les fausses alertes, documenter ce qui a été fait, puis clôturer et produire un rapport.

## Comment ça marche, en bref

1. Un **collecteur** récupère régulièrement les alertes critiques de FortiAnalyzer, sans créer de doublons.
2. Les **logs** sont indexés dans OpenSearch (recherche rapide) ; les **informations de suivi** vont dans PostgreSQL.
3. Les analystes travaillent dans **une seule application** qui combine les deux.

## Ce qui existe aujourd'hui

Les fondations (Docker, base de données à 3 tables) et un **premier socle métier côté serveur** (pas encore d'écran) :

- consulter l'**historique des imports** ;
- consulter les **logs** connus, avec filtres ;
- **créer et suivre un incident** à partir d'un log : statut, criticité réévaluée, faux positif justifié, responsable,
  clôture et réouverture.

La **collecte réelle depuis FortiAnalyzer n'existe pas encore** : son API doit d'abord être étudiée. Les tests utilisent
des données inventées, clairement marquées comme telles. Détail : [Traitement des incidents](./incident_workflow.md).

**Pas prêt pour la production** : il n'y a encore ni connexion des utilisateurs, ni contrôle des droits.

## Les trois tables

- **Imports** : l'historique des collectes (réussies ou échouées, combien de logs).
- **Logs** : les alertes connues. La criticité d'origine de FortiAnalyzer n'est jamais perdue.
- **Incidents** : le dossier de traitement d'une alerte (statut, criticité réévaluée, faux positif, responsable).

## Pour aller plus loin

[Architecture technique](../technical/architecture.md) · [Base de données](../technical/database.md) · [Cadrage complet](../../explain_project.md)
