# Les outils du projet — vue simple

Cette page explique, sans jargon, quels outils fait tourner Intelligentsia SOC et à quoi chacun sert.
Le détail technique (versions, fichiers, commandes) est dans [docs/technical/tools.md](../technical/tools.md).

## L'image d'ensemble

```
FortiAnalyzer ──► Collecteur ──► OpenSearch (recherche dans les logs)
   (à venir)       (à venir)  └─► PostgreSQL (incidents, imports) ──► API ──► Écrans analyste
                                     (en place)                      (en place)   (à venir)
```

## Ce qui est déjà en place

| Outil | En une phrase | À quel moment il sert |
|---|---|---|
| **Python** | Le langage dans lequel l'application est écrite. | Partout. |
| **FastAPI** | Fournit l'« API » : les adresses web que les écrans et outils appellent pour lire ou modifier les incidents. | À chaque demande faite à l'application. |
| **Uvicorn** | Le moteur qui fait tourner l'API et écoute les demandes. | Au démarrage de l'application. |
| **Pydantic** | Le contrôleur à l'entrée : il refuse les données mal formées (date sans fuseau, champ inconnu, justification manquante...). | À chaque donnée qui entre. |
| **PostgreSQL** | La base de données : elle garde l'historique des imports, les alertes connues et les incidents. | En permanence. |
| **SQLAlchemy** | Le traducteur entre le code Python et la base de données. | À chaque lecture/écriture en base. |
| **Alembic** | Le carnet des modifications de la base : chaque changement de structure est noté et rejouable. | Quand la structure de la base évolue, et au démarrage. |
| **Docker / Docker Compose** | Lance la base et l'application dans des « boîtes » identiques sur tous les postes. | Pour travailler en local. Sur ce poste, Docker tourne dans WSL. |
| **pytest** | Lance les tests automatiques qui vérifient que tout fonctionne. | Avant chaque envoi de code. |
| **Git / GitHub** | Garde l'historique du code et permet de travailler sur des branches. | À chaque enregistrement de travail. |

À noter : **SQLite** n'est utilisé que pour des tests rapides. La vraie base de l'application est PostgreSQL, et
l'application a été vérifiée sur PostgreSQL.

## Ce qui est prévu mais pas encore branché

| Outil | À quoi il servira | Ce qui manque pour l'ajouter |
|---|---|---|
| **FortiAnalyzer** | La source des alertes de sécurité. Il reste la référence d'origine. | La documentation de son API, le mode de connexion, un exemple de données anonymisé. |
| **Collecteur** | Le programme qui ira chercher les alertes dans FortiAnalyzer, sans jamais créer de doublon. | Les informations FortiAnalyzer ci-dessus. |
| **OpenSearch** | Ranger et rechercher rapidement dans de gros volumes de logs. | Décider où garder les logs complets. |
| **OpenSearch Dashboards** | Explorer les logs de façon technique, à côté de l'application. | OpenSearch en place. |
| **Data Prepper** | Transformer les logs en chemin, si le besoin apparaît. | Une décision : il est facultatif. |
| **Écrans analyste** | L'interface pour traiter les incidents. | La connexion des utilisateurs et les droits d'accès. |

## Ce qu'il faut retenir

- Chaque outil a **une place précise** ; un outil n'est ajouté que lorsqu'une fonctionnalité en a réellement besoin.
- Les mots de passe et jetons ne sont **jamais** écrits dans le code : ils vont dans un fichier `.env` local, non partagé.
- L'application **n'est pas prête pour la production** : il manque la connexion des utilisateurs, les droits d'accès
  et la sécurisation.
