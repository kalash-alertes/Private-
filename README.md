\# Conception initiale de la base de données — Application de gestion des alertes FortiAnalyzer



\## 1. Choix technologique



Nous avons choisi \*\*PostgreSQL\*\* comme système de gestion de base de données relationnelle. Il permettra de stocker les alertes récupérées depuis FortiAnalyzer et de conserver les informations nécessaires à leur suivi.



Pour la première version (V1), nous avons décidé de commencer avec \*\*trois tables principales\*\*, afin de garder une structure simple et de pouvoir la faire évoluer selon les besoins du projet.



\## 2. Les trois tables retenues



\### Table 1 : `logs`



Cette table stockera les logs critiques récupérés depuis l'API de FortiAnalyzer.



Elle contiendra notamment :

\- L'identifiant du log provenant de FortiAnalyzer ;

\- La date et l'heure de l'événement ;

\- Le type et la criticité initiale du log ;

\- Les données utiles de l'événement ;

\- La date et l'heure d'enregistrement dans notre base de données.



\*\*Objectif :\*\* conserver les informations utiles des alertes critiques sans recopier l'ensemble des logs de FortiAnalyzer.



\### Table 2 : `incidents`



Cette table permettra de suivre les incidents issus des alertes récupérées.



Elle contiendra notamment :

\- La référence du log à l'origine de l'incident ;

\- Le statut de l'incident ;

\- La criticité initiale et la criticité réévaluée ;

\- L'indication permettant de marquer un faux positif ;

\- Les informations nécessaires au suivi du traitement.



\*\*Objectif :\*\* distinguer l'événement technique de l'incident que les analystes doivent examiner, qualifier et traiter.



\### Table 3 : `executions\_import`



Cette table enregistrera les opérations de récupération des données depuis l'API FortiAnalyzer.



Elle contiendra notamment :

\- La date et l'heure de début et de fin de chaque import ;

\- Le statut de l'opération ;

\- Le nombre de logs reçus et enregistrés ;

\- Les informations de synchronisation nécessaires à la prochaine récupération.



\*\*Objectif :\*\* suivre les imports, planifier les récupérations périodiques et éviter de perdre ou de traiter plusieurs fois les mêmes alertes.



\## 3. Principe de fonctionnement



1\. L'application interroge périodiquement l'API FortiAnalyzer.

2\. Elle récupère uniquement les logs correspondant au niveau critique retenu pour la V1.

3\. Elle enregistre l'exécution de l'import et les logs reçus dans PostgreSQL.

4\. Les logs pertinents donnent lieu à des incidents qui pourront être qualifiés et suivis.

5\. Les analystes pourront ensuite réévaluer la criticité, identifier les faux positifs et traiter les incidents.



\## 4. Pourquoi commencer avec trois tables ?



Cette structure constitue une base minimale pour démarrer le projet. Elle évite de complexifier prématurément le modèle tout en séparant trois responsabilités : \*\*les événements techniques, le suivi des incidents et la synchronisation avec FortiAnalyzer\*\*.



Les fonctionnalités plus avancées — gestion des utilisateurs, tickets, escalades, playbooks, documentation et rapports — seront intégrées progressivement. Elles pourront nécessiter de nouvelles tables lorsque nous concevrons leur fonctionnement détaillé.



\## 5. Décision de conception à retenir



La base de données sera conçue pour évoluer. Les trois tables constituent le périmètre initial, et non une limite définitive du modèle. Nous conserverons également l'identifiant source des logs et prévoirons un mécanisme de détection des doublons lors des imports.



\*\*Décision retenue : PostgreSQL, trois tables initiales (`logs`, `incidents`, `executions\_import`) et une récupération périodique des seuls logs critiques de FortiAnalyzer.\*\*

