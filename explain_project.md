# Explain Project --- Application de gestion des alertes et incidents FortiAnalyzer

**Document de cadrage technique et fonctionnel --- Version 1**

Ce document rassemble la vision du projet, les composants envisagés,
leurs responsabilités, les flux de données, le modèle de données initial
et l'ordre recommandé pour commencer le développement. Il sert de
référence de départ. Les choix présentés comme « recommandés » restent à
valider au fur et à mesure de la conception.

------------------------------------------------------------------------

## 1. Présentation du projet

Le projet consiste à développer une application qui aide une équipe de
sécurité à traiter les alertes critiques remontées par
**FortiAnalyzer**.

L'objectif n'est pas simplement d'afficher des logs. L'application doit
accompagner le travail opérationnel d'un analyste : récupérer les
alertes, les retrouver facilement, ouvrir et suivre les incidents,
évaluer leur gravité, attribuer le travail à une personne, documenter
l'investigation, suivre un plan de réponse et produire un rapport.

### Problème à résoudre

Des logs de sécurité peuvent signaler un événement intéressant, mais un
log seul ne constitue pas toujours un incident entièrement traité.
L'équipe doit pouvoir répondre à des questions telles que :

-   Quelle alerte a été détectée et quand ?
-   Quelle est sa criticité d'origine dans FortiAnalyzer ?
-   Est-ce un véritable incident ou un faux positif ?
-   Qui est responsable de son traitement ?
-   Quelles vérifications faut-il réaliser ?
-   Quelles actions de réponse sont recommandées et sur quelle
    documentation s'appuient-elles ?
-   Quel a été le résultat de l'investigation ?
-   Quand l'incident a-t-il été clôturé et quel rapport peut-on produire
    ?

L'application doit centraliser ce processus, sans remplacer
FortiAnalyzer comme source d'origine des alertes.

------------------------------------------------------------------------

## 2. Objectifs de la première version (V1)

La V1 doit rester volontairement limitée afin de pouvoir être
construite, testée et comprise progressivement.

### Fonctions prévues

1.  **Collecter les logs critiques** depuis l'API de FortiAnalyzer.
2.  **Éviter les doublons** lorsque la même alerte est rencontrée
    plusieurs fois.
3.  **Conserver les informations utiles** sur les logs collectés et
    l'exécution des imports.
4.  **Permettre de créer et suivre un incident** à partir d'un log.
5.  **Gérer l'état d'un incident**, par exemple : nouveau, en cours, en
    attente, résolu ou clôturé. Les valeurs exactes seront à définir.
6.  **Réévaluer la criticité** d'un incident à la hausse ou à la baisse,
    sans perdre la criticité d'origine de FortiAnalyzer.
7.  **Marquer un incident comme faux positif**, avec une justification.
8.  **Attribuer un incident** à une personne et gérer un suivi de type
    ticket.
9.  **Définir des procédures ou playbooks** adaptés au type de problème,
    avec des étapes de vérification et des actions.
10. **Fonder les plans de réponse sur des sources fiables** :
    documentation officielle, procédures internes validées ou références
    vérifiables. L'application ne doit pas présenter une procédure
    inventée comme une vérité établie.
11. **Documenter l'investigation**, les décisions prises et le résultat.
12. **Produire un rapport** à la fin du traitement ou à la clôture de
    l'incident.
13. **Afficher l'historique des imports**, notamment les réussites, les
    échecs et les nombres de logs traités.

### Ce qui n'est pas nécessaire immédiatement

Pour éviter de rendre la V1 trop complexe, il est préférable de ne pas
commencer par :

-   un système très sophistiqué de playbooks automatisés ;
-   des actions de réponse exécutées automatiquement sur
    l'infrastructure ;
-   une gestion complète de plusieurs organisations ou tenants ;
-   de nombreuses tables avant que les besoins soient confirmés ;
-   une duplication systématique de toutes les données complètes dans
    plusieurs bases ;
-   une intégration à de nombreux outils externes avant d'avoir validé
    le flux de base.

Ces possibilités pourront être étudiées dans une version ultérieure.

------------------------------------------------------------------------

## 3. Vue d'ensemble de l'architecture

Les composants envisagés sont les suivants :

-   **FortiAnalyzer** : source des événements et logs de sécurité.
-   **Collecteur personnalisé** : programme développé pour interroger
    l'API de FortiAnalyzer et récupérer les logs nécessaires.
-   **Data Prepper** : composant optionnel qui peut transformer ou
    acheminer les événements avant leur indexation.
-   **OpenSearch** : moteur de recherche et de stockage indexé pour les
    logs.
-   **OpenSearch Dashboards** : interface de consultation et
    d'exploration technique des logs dans OpenSearch.
-   **PostgreSQL** : base relationnelle pour les incidents, l'état
    métier et le suivi des imports.
-   **Application personnalisée** : interface destinée aux analystes
    pour gérer les incidents et leur cycle de traitement.

Schéma logique :

``` text
                         ┌────────────────────┐
                         │    FortiAnalyzer   │
                         │ API / logs sécurité│
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │ Collecteur maison  │
                         │ API, pagination,   │
                         │ filtres, dédoublon │
                         └─────────┬──────────┘
                                   │
                         Normalisation éventuelle
                         dans le collecteur
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          ┌──────────────────┐          ┌──────────────────┐
          │   OpenSearch     │          │   PostgreSQL     │
          │ Logs indexés et  │          │ Incidents, liens │
          │ recherchables    │          │ et imports       │
          └────────┬─────────┘          └────────┬─────────┘
                   │                             │
          ┌────────▼─────────┐          ┌────────▼─────────┐
          │ OpenSearch       │          │ Application      │
          │ Dashboards       │          │ personnalisée    │
          │ Exploration logs │          │ Workflow incident│
          └──────────────────┘          └──────────────────┘
```

**Option Data Prepper :** il peut être ajouté entre le collecteur et
OpenSearch si les transformations, les pipelines ou les volumes le
justifient. Il n'est pas obligatoire pour démarrer. Une première version
peut normaliser les données directement dans le collecteur.

Le schéma est logique : les connexions exactes, les protocoles, les
déploiements et les mécanismes de reprise devront être précisés pendant
la conception technique.

------------------------------------------------------------------------

## 4. Rôle de chaque composant

### 4.1 FortiAnalyzer

FortiAnalyzer est la source de données. Il reçoit et conserve les
événements issus des équipements Fortinet selon la configuration en
place.

Dans ce projet, FortiAnalyzer reste le système d'origine. L'application
ne doit pas prétendre être la source du log : elle en récupère une copie
ou les champs utiles pour permettre l'analyse et le suivi des incidents.

Avant d'écrire le collecteur, il faudra étudier la version utilisée, les
méthodes d'authentification, les endpoints disponibles, les filtres, la
pagination et les limites de l'API. Il ne faut pas inventer les noms
d'endpoints ou les paramètres : ils doivent être vérifiés dans la
documentation correspondant à la version installée.

### 4.2 Collecteur personnalisé

Le collecteur est un programme que nous allons développer. Ce n'est ni
une base de données ni une interface graphique.

Ses responsabilités prévues sont :

1.  s'authentifier auprès de l'API FortiAnalyzer ;
2.  interroger les données selon une période ou un curseur de
    synchronisation ;
3.  récupérer uniquement les événements répondant au périmètre V1,
    notamment la criticité critique ;
4.  gérer la pagination si l'API renvoie les résultats par pages ;
5.  normaliser les champs nécessaires sans déformer le contenu d'origine
    ;
6.  identifier les événements de manière stable pour éviter les doublons
    ;
7.  transmettre les logs à OpenSearch et enregistrer les métadonnées
    d'import dans PostgreSQL ;
8.  journaliser les erreurs et permettre une reprise après échec.

Il faut prévoir les erreurs réseau, les expirations de session, les
réponses API inattendues et les interruptions partielles. Un import
interrompu ne doit pas conduire à considérer que tous les logs ont été
enregistrés avec succès.

**Point important :** l'envoi vers OpenSearch et l'enregistrement dans
PostgreSQL ne forment pas automatiquement une transaction commune. Il
faudra donc concevoir des opérations idempotentes, des identifiants
stables, des statuts d'import et une stratégie de reprise. Le système
doit pouvoir retenter un envoi sans créer des doublons.

### 4.3 OpenSearch

OpenSearch est un **service serveur autonome** de recherche et
d'indexation, et non une simple bibliothèque que l'on importe dans le
code.

Il conserve des documents, généralement structurés en JSON, dans des
**index**. Il construit des structures d'indexation qui permettent de
rechercher et filtrer rapidement les champs pertinents.

Exemple conceptuel d'un document de log :

``` json
{
  "event_id": "identifiant-stable-de-l-evenement",
  "event_time": "2026-10-28T10:15:00Z",
  "severity": "critical",
  "source": "FortiAnalyzer",
  "event_type": "exemple",
  "raw_event": {
    "champ_original": "valeur originale"
  }
}
```

Cet exemple illustre la forme possible des données ; ce n'est pas un
format imposé par FortiAnalyzer. Les champs exacts seront définis après
inspection de vrais résultats de l'API.

OpenSearch est adapté aux besoins de recherche tels que :

-   retrouver des logs sur une période ;
-   filtrer par adresse IP, équipement, type d'événement ou criticité ;
-   rechercher des valeurs dans les champs indexés ;
-   explorer des événements liés à une investigation ;
-   alimenter des tableaux de bord techniques.

Une bibliothèque cliente Python, JavaScript ou autre peut être utilisée
par l'application pour envoyer des requêtes à OpenSearch. La
bibliothèque est seulement le moyen de communiquer avec le serveur : le
stockage et la recherche sont assurés par le service OpenSearch
lui-même.

### 4.4 OpenSearch Dashboards

> **Mise à jour du 2026-10-29** : OpenSearch Dashboards n'est plus prévu comme interface. L'interface des analystes
> est rendue en Python par le backend (`web_interface/`), avec le visuel de la maquette de l'équipe. Voir
> [docs/technical/web_interface.md](./docs/technical/web_interface.md). Le texte ci-dessous est conservé pour
> l'historique du cadrage.

OpenSearch Dashboards est l'interface graphique qui permet de consulter
et d'explorer les données d'OpenSearch.

Elle est utile aux personnes qui doivent examiner les logs en détail,
construire des recherches, visualiser des tendances ou préparer des
tableaux de bord techniques.

Elle ne remplace pas l'application personnalisée. Par exemple, elle
n'est pas nécessairement l'endroit où l'on gère le responsable d'un
incident, sa justification de faux positif, son plan de réponse ou son
rapport final. Ces fonctions relèvent de l'application métier.

Les deux interfaces peuvent donc coexister : - OpenSearch Dashboards
pour l'exploration technique des logs ; - l'application personnalisée
pour le workflow de traitement des incidents.

### 4.5 PostgreSQL

PostgreSQL est la base relationnelle destinée aux données métier et au
suivi du processus.

Pour la V1, le modèle de départ envisagé comporte trois tables :

-   `logs` : métadonnées du log collecté et référence vers son document
    dans OpenSearch, si cette architecture est retenue ;
-   `incidents` : état métier et traitement de l'incident ;
-   `executions_import` : historique des tentatives et exécutions de
    collecte.

PostgreSQL est adapté aux relations, contraintes, mises à jour
cohérentes et requêtes portant sur les incidents.

Il est recommandé d'en faire la **source de vérité du workflow** :
statut, criticité réévaluée, attribution, faux positif et clôture sont
des informations métier. OpenSearch reste le moteur principal de
recherche technique sur les logs.

### 4.6 Application personnalisée

L'application personnalisée sera l'interface utilisée par l'analyste
pour effectuer le travail opérationnel.

Les écrans à prévoir pourront inclure :

-   un tableau de bord des incidents ;
-   une liste et une fiche détaillée d'incident ;
-   l'accès au log associé ;
-   la modification de la criticité ;
-   le statut et l'attribution ;
-   la qualification faux positif avec justification ;
-   les étapes d'investigation et les notes ;
-   les références documentaires utilisées ;
-   la clôture et la génération d'un rapport ;
-   un écran d'état des imports et des erreurs de collecte.

La technologie de frontend et de backend n'est pas encore arrêtée dans
ce document. Il faut d'abord inspecter le dépôt existant et conserver sa
stack lorsqu'elle est déjà adaptée, plutôt que choisir arbitrairement un
nouveau framework.

------------------------------------------------------------------------

## 5. Pourquoi utiliser OpenSearch et PostgreSQL ensemble ?

Les deux systèmes n'ont pas le même rôle.

  -----------------------------------------------------------------------
  Besoin                  Outil recommandé        Raison
  ----------------------- ----------------------- -----------------------
  Rechercher rapidement   OpenSearch              Moteur d'indexation et
  dans de nombreux logs                           de recherche

  Explorer les logs dans  OpenSearch Dashboards   Interface de
  une interface technique                         consultation

  Suivre le statut d'un   PostgreSQL              Données relationnelles
  incident                                        et contraintes

  Enregistrer le          PostgreSQL              Informations métier
  responsable et la                               structurées
  justification                                   

  Conserver les           PostgreSQL              Historique relationnel
  tentatives d'import                             des exécutions

  Produire une vue        Application             Interface adaptée au
  opérationnelle de       personnalisée           workflow
  l'incident                                      
  -----------------------------------------------------------------------

### Éviter la duplication inutile

Une décision d'architecture importante consiste à éviter de conserver
systématiquement le même log complet dans PostgreSQL et OpenSearch.

Une approche recommandée est :

-   OpenSearch conserve le document complet du log et les champs indexés
    ;
-   PostgreSQL conserve les métadonnées nécessaires à l'application, les
    relations et une référence stable vers le document OpenSearch ;
-   l'application interroge PostgreSQL pour le workflow d'incident et
    OpenSearch pour les détails ou recherches techniques.

Cela évite que deux copies complètes divergent et réduit la duplication.
Toutefois, il faut décider si certains champs ou une copie minimale du
log doivent aussi être conservés dans PostgreSQL pour l'audit, la
résilience ou les exigences du projet.

**Alternative possible :** si la V1 ne collecte qu'un très faible volume
de logs critiques et que les besoins de recherche sont simples, il peut
être plus facile de commencer avec PostgreSQL seul. OpenSearch apporte
de la valeur si les recherches dans les logs, les filtres, les
agrégations et les tableaux de bord justifient le service
supplémentaire. Il est donc utile de valider le besoin avant d'imposer
toute la complexité de la pile.

------------------------------------------------------------------------

## 6. Flux de données et de traitement

### Étape 1 --- Collecte

Le collecteur interroge FortiAnalyzer et récupère les événements
correspondant au périmètre défini. Pour la V1, le périmètre initial est
limité aux logs critiques.

### Étape 2 --- Contrôle et normalisation

Le collecteur vérifie que les données sont exploitables, extrait les
champs nécessaires et conserve les valeurs d'origine utiles à l'audit.
La normalisation doit être documentée pour ne pas confondre la criticité
source et la criticité réévaluée par un analyste.

### Étape 3 --- Déduplication

Chaque événement doit disposer d'un identifiant source stable si
FortiAnalyzer en fournit un. Si aucun identifiant stable n'existe, il
faudra définir une stratégie de déduplication fondée sur les champs
réellement disponibles. Il ne faut pas supposer qu'une combinaison de
champs est unique sans le vérifier.

### Étape 4 --- Indexation dans OpenSearch

Le log est envoyé à OpenSearch avec un identifiant de document
déterministe lorsque c'est possible. Une nouvelle tentative d'envoi du
même événement ne doit pas créer un nouveau document identique.

### Étape 5 --- Enregistrement de l'import dans PostgreSQL

Une exécution d'import est créée et mise à jour avec son état, ses
dates, les nombres d'événements reçus, insérés ou ignorés, et l'erreur
éventuelle.

La définition exacte de « reçu », « inséré » et « ignoré » doit être
précisée. Les compteurs doivent refléter les résultats réels et non
simplement le nombre de requêtes tentées.

### Étape 6 --- Consultation

L'analyste retrouve les logs dans l'application ou dans OpenSearch
Dashboards selon son besoin. L'application peut afficher les métadonnées
du log et demander à OpenSearch le document détaillé.

### Étape 7 --- Création et traitement d'un incident

Lorsqu'un log nécessite un traitement, un incident est créé ou relié à
ce log. L'analyste évalue la gravité, attribue l'incident, effectue les
vérifications et documente ses décisions.

Un log n'est pas automatiquement synonyme d'incident : la règle de
création d'incident devra être définie. Pour la V1, le modèle envisagé
autorise au maximum un incident par log.

### Étape 8 --- Réponse, clôture et rapport

L'analyste suit les étapes de réponse adaptées au cas, consigne les
résultats et références documentaires, puis clôture l'incident lorsque
les conditions définies sont remplies. Un rapport peut ensuite être
généré à partir des données documentées.

------------------------------------------------------------------------

## 7. Modèle de données initial : trois tables

Le modèle de départ est volontairement limité à trois tables. Les
détails techniques seront définis dans la migration de base de données.

### 7.1 `executions_import`

Cette table représente une tentative ou exécution de collecte.

Champs envisagés :

  -----------------------------------------------------------------------
  Champ                               Rôle
  ----------------------------------- -----------------------------------
  `id`                                Identifiant UUID de l'exécution

  `debut`                             Date/heure de début

  `fin`                               Date/heure de fin, nulle tant que
                                      l'exécution n'est pas terminée

  `statut`                            État de l'exécution : en cours,
                                      réussie, partielle ou échouée, par
                                      exemple

  `nb_logs_recus`                     Nombre de logs reçus de la source

  `nb_logs_inseres`                   Nombre de logs effectivement
                                      enregistrés selon la définition
                                      retenue

  `nb_logs_ignores`                   Nombre de logs ignorés, par exemple
                                      car déjà connus

  `erreur`                            Détail de l'erreur éventuelle

  `curseur_synchronisation`           Valeur permettant de reprendre la
                                      synchronisation si l'API le permet

  `created_at`                        Date de création de
                                      l'enregistrement
  -----------------------------------------------------------------------

Le curseur exact dépendra de l'API FortiAnalyzer : il pourrait s'agir
d'un timestamp, d'un identifiant ou d'un autre mécanisme. Il ne faut pas
supposer que le timestamp seul permet une synchronisation sans perte.

### 7.2 `logs`

Cette table représente les logs connus par l'application. Dans
l'architecture avec OpenSearch, elle contient surtout les métadonnées et
la référence vers le document indexé, plutôt qu'une seconde copie
complète du log.

Champs envisagés :

  -----------------------------------------------------------------------
  Champ                               Rôle
  ----------------------------------- -----------------------------------
  `id`                                Identifiant UUID interne

  `identifiant_source`                Identifiant stable de l'événement
                                      source, s'il existe

  `date_evenement`                    Date/heure de l'événement dans le
                                      log

  `type`                              Type ou catégorie d'événement

  `criticite_source`                  Criticité originale provenant de
                                      FortiAnalyzer

  `donnees_brutes`                    JSONB si une copie brute est
                                      nécessaire ; à décider selon la
                                      stratégie de stockage

  `reference_opensearch`              Identifiant ou référence permettant
                                      de retrouver le document dans
                                      OpenSearch, si OpenSearch est
                                      retenu

  `arrivee_db`                        Date/heure d'enregistrement dans
                                      PostgreSQL

  `execution_import_id`               Référence vers l'exécution qui a
                                      enregistré le log pour la première
                                      fois
  -----------------------------------------------------------------------

Le champ `reference_opensearch` est une proposition utile si OpenSearch
stocke le document complet. Si la stratégie finale conserve les logs
uniquement dans PostgreSQL, ce champ ne sera pas nécessaire. De même, il
faudra décider si `donnees_brutes` contient tout le log, une copie
réduite ou aucune copie brute.

**Déduplication :** prévoir une contrainte d'unicité sur un identifiant
source réellement stable. Si la source ne fournit pas cet identifiant,
définir et documenter une autre clé fiable après examen des données.

### 7.3 `incidents`

Cette table représente le suivi métier d'un incident issu d'un log.

Champs envisagés :

  -----------------------------------------------------------------------
  Champ                               Rôle
  ----------------------------------- -----------------------------------
  `id`                                Identifiant UUID de l'incident

  `log_id`                            Référence au log à l'origine de
                                      l'incident

  `statut`                            État du traitement

  `criticite_actuelle`                Criticité évaluée par l'équipe

  `faux_positif`                      Indique si l'incident est qualifié
                                      de faux positif

  `justification`                     Motif de la qualification ou de la
                                      décision

  `assigne_a`                         Identifiant du responsable, à
                                      définir selon le système
                                      d'authentification

  `created_at`                        Date de création

  `updated_at`                        Date de dernière mise à jour

  `closed_at`                         Date de clôture, nulle tant que
                                      l'incident est ouvert
  -----------------------------------------------------------------------

Le champ `assigne_a` est une proposition fonctionnelle utile, mais son
type et sa cible dépendront de la façon dont les utilisateurs seront
gérés. Le modèle initial reste limité à trois tables ; il ne faut pas
créer automatiquement une table utilisateurs avant d'avoir choisi le
mécanisme d'identité et d'authentification.

Le modèle envisagé utilise une contrainte d'unicité sur `log_id`, ce qui
signifie qu'un log peut être lié à zéro ou un incident dans la V1. Si
l'on veut plus tard plusieurs incidents pour un seul log, il faudra
réviser ce choix.

### Relations

``` mermaid
erDiagram
    EXECUTIONS_IMPORT ||--o{ LOGS : "importe"
    LOGS ||--o| INCIDENTS : "peut déclencher"
```

-   Une exécution d'import peut enregistrer plusieurs logs.
-   Chaque log conservé est rattaché à une exécution d'import initiale.
-   Un log peut n'avoir aucun incident ou être lié à un seul incident
    dans la V1.

Si un même log est retrouvé lors d'une exécution ultérieure, il ne faut
pas créer un second log uniquement pour le rattacher à la nouvelle
exécution. Le log existant reste unique. Les compteurs de l'exécution
ultérieure doivent indiquer qu'il a été ignoré comme doublon, ou la
conception devra évoluer si un historique complet des apparitions par
import devient nécessaire.

### Contraintes et index à envisager

-   Clés primaires UUID.
-   Clés étrangères entre les trois tables.
-   Dates stockées avec fuseau horaire, par exemple `TIMESTAMPTZ` dans
    PostgreSQL.
-   Contraintes contrôlant les statuts et les valeurs de criticité.
-   Unicité de l'identifiant source lorsqu'il est fiable.
-   Unicité de `incidents.log_id` si la règle « un incident maximum par
    log » est conservée.
-   Index sur la date de l'événement, la criticité source, le statut
    d'incident et les clés étrangères utilisées dans les recherches.
-   Valeurs JSONB uniquement si elles répondent à un besoin précis ;
    elles ne doivent pas remplacer arbitrairement des colonnes
    relationnelles importantes.

------------------------------------------------------------------------

## 8. Distinguer la criticité source et la criticité actuelle

Il est essentiel de conserver deux notions séparées :

-   **Criticité source** : valeur fournie par FortiAnalyzer au moment de
    la collecte.
-   **Criticité actuelle** : évaluation utilisée par l'équipe pour
    piloter le traitement de l'incident.

Exemple conceptuel :

-   FortiAnalyzer classe une alerte comme critique.
-   Après analyse, l'analyste estime que le risque réel est plus faible.
-   L'incident est réévalué à une criticité inférieure, avec une
    justification.
-   La criticité originale reste conservée afin de savoir ce que la
    source avait signalé.

L'inverse est également possible : une alerte peut être jugée plus grave
après investigation.

Pour garder une trace fiable des changements, un historique complet des
modifications de criticité serait utile. Cependant, le modèle initial à
trois tables ne possède pas encore de table d'audit. Pour la V1, il
faudra décider si la justification et les dates de mise à jour suffisent
temporairement, ou si l'historique doit être ajouté avant le
développement. Il ne faut pas prétendre disposer d'un historique complet
si seules les valeurs actuelles sont enregistrées.

------------------------------------------------------------------------

## 9. Faux positifs, tickets et attribution

### Faux positif

Lorsqu'un incident est qualifié de faux positif, l'application doit
enregistrer cette décision et une justification. Il faut éviter qu'un
simple bouton efface toute trace de l'événement.

Le traitement d'un faux positif doit rester cohérent avec le statut de
l'incident. La règle exacte --- par exemple un statut dédié ou une
combinaison du statut et du booléen `faux_positif` --- devra être
définie pour éviter les états contradictoires.

### Attribution et ticketing

L'incident doit pouvoir être assigné à une personne, avec un statut
clair et des informations de suivi.

Pour une V1 simple, l'application peut gérer les tickets directement
dans la table `incidents`. Si des commentaires multiples, des pièces
jointes, des changements de responsable ou un historique détaillé
deviennent nécessaires, trois tables risquent de ne plus suffire. Ces
besoins devront être évalués avant de figer le schéma définitif.

------------------------------------------------------------------------

## 10. Playbooks et plans de réponse documentés

Un playbook est une procédure structurée pour traiter un type
d'incident. Il peut contenir :

1.  le type d'incident concerné ;
2.  les conditions qui justifient son utilisation ;
3.  les vérifications initiales ;
4.  les éléments à collecter ;
5.  les actions recommandées ;
6.  les critères d'escalade ;
7.  les conditions de résolution ou de clôture ;
8.  les sources de référence ;
9.  les avertissements et prérequis.

### Exigence de traçabilité

Les procédures ne doivent pas être présentées comme des faits fiables si
aucune source ne les justifie. Les références peuvent provenir, selon le
cas, de documentations officielles de l'éditeur, de standards reconnus
ou de procédures internes validées.

Pour chaque référence, conserver au minimum : - le titre de la source
; - l'organisation ou l'auteur ; - l'URL ou la référence documentaire
; - la date de consultation si pertinente ; - la partie ou le passage
qui justifie l'étape ; - les limites ou conditions d'application.

Une source externe ne garantit pas à elle seule que l'action convient à
l'environnement. Les procédures doivent être adaptées au contexte et
validées avant toute action sensible.

### Limite du modèle de données initial

Les trois tables actuelles ne représentent pas encore les playbooks,
leurs étapes, les sources documentaires ou les notes détaillées
d'investigation. Ce sont des fonctions prévues dans la vision du
produit, mais elles nécessiteront une décision de conception
supplémentaire. Il ne faut pas les faire apparaître comme déjà prises en
charge par le schéma à trois tables.

Une décision à prendre avant l'implémentation de ces fonctions :
accepter une V1 de base limitée à la collecte et au cycle de vie des
incidents, puis ajouter les tables nécessaires aux playbooks, notes et
rapports ; ou étendre le schéma initial dès le départ. La contrainte «
trois tables » doit être comprise comme le modèle initial demandé, pas
comme une preuve que toutes les fonctionnalités avancées peuvent être
modélisées proprement avec trois tables seulement.

------------------------------------------------------------------------

## 11. Rapports de fin d'incident

Le rapport doit refléter ce qui a réellement été constaté et réalisé,
sans transformer une hypothèse en certitude.

Un rapport pourra contenir : - un identifiant d'incident ; - les dates
de détection, de prise en charge et de clôture ; - la criticité source
et la criticité finale ; - une description synthétique de l'événement
; - le responsable du traitement ; - les observations et vérifications
effectuées ; - les actions menées et leurs résultats ; - la
qualification éventuelle de faux positif et sa justification ; - les
références documentaires utilisées ; - le résultat final et les
éventuelles recommandations.

Le format exact (HTML, PDF ou autre) reste à décider. Il faut aussi
décider si le rapport est généré à la demande ou archivé au moment de la
clôture.

------------------------------------------------------------------------

## 12. Sécurité et fiabilité à prévoir

Même dans une V1, certains principes ne doivent pas être négligés :

-   Ne pas coder en dur les mots de passe, jetons API ou clés secrètes.
-   Utiliser des variables d'environnement ou un gestionnaire de secrets
    adapté au déploiement.
-   Ne pas afficher les secrets dans les logs de l'application.
-   Protéger l'accès à l'application et aux bases de données.
-   Limiter les permissions du compte API FortiAnalyzer au strict
    nécessaire.
-   Utiliser TLS lorsque le contexte de déploiement le permet et
    configurer correctement les certificats.
-   Valider les données reçues de l'API.
-   Limiter l'exposition réseau d'OpenSearch et PostgreSQL ; ils ne
    doivent pas être ouverts publiquement sans besoin et protections
    adaptés.
-   Enregistrer les erreurs utiles au diagnostic sans divulguer de
    secrets.
-   Prévoir les sauvegardes et la restauration des données métier.
-   Définir une politique de rétention des logs et rapports.
-   Vérifier les horodatages et fuseaux horaires pour éviter les erreurs
    de chronologie.
-   Rendre les imports idempotents et testables.
-   Ne pas automatiser des actions destructrices sur les systèmes de
    production sans garde-fous, validation et autorisation explicites.

------------------------------------------------------------------------

## 13. Ordre recommandé de développement

Il vaut mieux avancer par étapes avec un résultat testable à chaque
phase.

### Phase 1 --- Comprendre l'existant et fixer le périmètre

-   Examiner le dépôt et identifier la stack déjà utilisée.
-   Identifier les versions de FortiAnalyzer et les capacités de son
    API.
-   Obtenir un exemple de réponse API réel, en masquant les données
    sensibles.
-   Définir précisément ce que signifie « critique » dans la source et
    comment le filtre sera appliqué.
-   Décider si OpenSearch est nécessaire dès la V1 ou s'il peut être
    ajouté après validation.

**Résultat attendu :** un périmètre V1 et des décisions documentées,
sans commencer prématurément à coder toutes les fonctionnalités.

### Phase 2 --- Concevoir la base PostgreSQL

-   Valider les trois tables initiales.
-   Décider du stockage complet ou partiel des logs.
-   Définir les clés étrangères, contraintes, index et statuts
    autorisés.
-   Clarifier l'identifiant source et la stratégie de déduplication.
-   Décider comment représenter l'attribution dans l'attente du choix
    d'authentification.
-   Préparer une migration versionnée et reproductible.

**Résultat attendu :** une base créable à partir d'une migration, avec
des contraintes cohérentes.

### Phase 3 --- Valider l'accès à FortiAnalyzer

-   Étudier la documentation API de la version réellement installée.
-   Valider l'authentification et les permissions.
-   Tester une requête en lecture seule.
-   Comprendre les filtres, la pagination, les horodatages et les
    limites de requêtes.
-   Définir la stratégie de reprise et le curseur de synchronisation.

**Résultat attendu :** une méthode documentée et vérifiée pour récupérer
les logs critiques.

### Phase 4 --- Construire le collecteur

-   Interroger l'API.
-   Filtrer et normaliser les logs.
-   Dédupliquer les événements.
-   Enregistrer les métadonnées d'import.
-   Envoyer les documents vers OpenSearch si cette option est confirmée.
-   Gérer les échecs partiels et les nouvelles tentatives.
-   Ajouter des tests sur les doublons, les erreurs et la reprise.

**Résultat attendu :** une collecte reproductible et observable.

### Phase 5 --- Construire la consultation des logs

-   Définir les champs indexés et les mappings OpenSearch.
-   Vérifier que les recherches usuelles fonctionnent.
-   Utiliser OpenSearch Dashboards pour explorer les logs.
-   Prévoir un lien entre un log PostgreSQL et son document OpenSearch.

**Résultat attendu :** les analystes peuvent retrouver et examiner les
logs collectés.

### Phase 6 --- Construire le workflow incident

-   Créer et afficher les incidents.
-   Mettre à jour les statuts.
-   Réévaluer la criticité en conservant celle de la source.
-   Attribuer les incidents.
-   Enregistrer les décisions de faux positif avec justification.
-   Définir les règles de clôture.

**Résultat attendu :** le traitement d'un incident est traçable au
niveau prévu par le modèle.

### Phase 7 --- Ajouter les playbooks et les rapports

-   Définir le format des procédures et étapes.
-   Ajouter les références documentaires traçables.
-   Décider comment conserver les notes et résultats d'investigation.
-   Générer un rapport de fin d'incident.
-   Ajouter les tables nécessaires si les fonctions ne peuvent pas être
    modélisées correctement dans les trois tables initiales.

**Résultat attendu :** les procédures et les résultats sont documentés
et réutilisables.

### Phase 8 --- Renforcer et déployer

-   Tester les erreurs réseau, les imports incomplets et les doublons.
-   Tester les permissions et l'accès aux données.
-   Configurer les sauvegardes et la rétention.
-   Documenter l'installation, la configuration et les opérations
    courantes.
-   Préparer des exemples de données non sensibles pour les tests et
    démonstrations.

------------------------------------------------------------------------

## 14. Tests d'acceptation de la V1

Avant de considérer la V1 comme fonctionnelle, vérifier au minimum les
scénarios suivants :

1.  Le collecteur peut s'authentifier et récupérer les logs avec les
    paramètres validés.
2.  Le périmètre critique est appliqué correctement.
3.  Une même alerte reçue plusieurs fois ne crée pas plusieurs
    enregistrements log.
4.  Une exécution réussie est enregistrée avec ses compteurs.
5.  Une exécution échouée ou partielle est identifiée comme telle et
    fournit une erreur exploitable.
6.  Un incident peut être créé à partir d'un log.
7.  La criticité source reste inchangée lorsque l'analyste réévalue
    l'incident.
8.  La criticité actuelle peut être augmentée ou diminuée selon les
    règles retenues.
9.  Un faux positif nécessite une justification.
10. Un incident peut être attribué et son statut mis à jour.
11. L'application peut retrouver le log détaillé associé.
12. La clôture permet de rassembler les informations nécessaires au
    rapport.
13. Les secrets ne sont pas présents dans le dépôt, les messages
    d'erreur ou les journaux.
14. Les tests ne sont déclarés réussis que s'ils ont réellement été
    exécutés.

------------------------------------------------------------------------

## 15. Décisions à confirmer avant d'aller trop loin

Quelques points doivent être clarifiés pendant la conception :

1.  **Stack existante :** quelle technologie le dépôt utilise-t-il déjà
    pour le backend et le frontend ?
2.  **FortiAnalyzer :** quelle version est installée et quelle API est
    disponible ?
3.  **Stockage :** OpenSearch est-il indispensable dès la V1, ou
    PostgreSQL suffit-il pour valider le flux avec les seuls logs
    critiques ?
4.  **Log brut :** faut-il garder le document complet dans OpenSearch
    seulement, ou également une copie dans PostgreSQL ?
5.  **Identifiant source :** quel champ identifie un événement de façon
    stable dans la réponse réelle de FortiAnalyzer ?
6.  **Authentification des utilisateurs :** comment les analystes se
    connecteront-ils et comment leur identité sera-t-elle représentée ?
7.  **Historique :** faut-il conserver les changements successifs de
    criticité, de responsable, de statut et les commentaires dans la V1
    ?
8.  **Playbooks :** les procédures sont-elles seulement affichées à
    l'analyste ou certaines étapes doivent-elles être exécutées
    automatiquement plus tard ?
9.  **Rapports :** quel format et quelles informations sont obligatoires
    ?
10. **Déploiement :** environnement local, machines virtuelles,
    conteneurs ou serveur dédié ?

Ces décisions ne doivent pas toutes bloquer la première migration. En
revanche, le stockage des logs, la déduplication et les capacités
réelles de l'API doivent être clarifiés tôt, car ils influencent
directement le collecteur et le schéma.

------------------------------------------------------------------------

## 16. Première tâche concrète

Pour commencer sans disperser le travail :

1.  Examiner le dépôt existant et comprendre sa structure.
2.  Documenter la stack et les commandes de lancement déjà disponibles.
3.  Vérifier la version de FortiAnalyzer et consulter la documentation
    API correspondante.
4.  Obtenir un exemple anonymisé de log et identifier ses champs.
5.  Valider le choix PostgreSQL seul ou PostgreSQL + OpenSearch.
6.  Finaliser la migration PostgreSQL initiale.
7.  Seulement ensuite, développer le collecteur.

**Règle de travail :** avancer par petites étapes vérifiables. Ne pas
implémenter tous les modules à la fois. Ne pas inventer les champs de
l'API ou les procédures de réponse. Ne pas annoncer un test comme réussi
s'il n'a pas été exécuté. Le développement du code commencera lorsque le
périmètre et les premières décisions seront suffisamment clairs.

------------------------------------------------------------------------

## Résumé final

Le projet est une application de gestion opérationnelle des incidents de
sécurité à partir des logs critiques de FortiAnalyzer.

-   FortiAnalyzer fournit les événements.
-   Le collecteur récupère, filtre, déduplique et transmet les
    événements.
-   OpenSearch, si retenu, stocke et indexe les logs pour les
    recherches.
-   OpenSearch Dashboards sert à l'exploration technique.
-   PostgreSQL conserve les informations métier et l'état des incidents.
-   L'application personnalisée permet aux analystes de suivre les
    incidents, d'en justifier les décisions, de documenter la réponse et
    de produire les rapports.
-   Data Prepper est une option, pas une obligation pour la première
    version.
-   Le modèle initial de base de données comprend trois tables, mais les
    playbooks détaillés, les notes et l'audit complet peuvent exiger une
    extension ultérieure.
-   Les sources des procédures doivent être traçables et les actions
    sensibles validées.

La meilleure façon de commencer est de valider le schéma, les données
réellement renvoyées par FortiAnalyzer et le besoin concret d'OpenSearch
avant d'implémenter tout le système.
