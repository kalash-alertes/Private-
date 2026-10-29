# Feature `playbooks`

**Rôle** : procédures de réponse (tables `playbooks`, `etapes_playbook`) : un nom unique, une **source obligatoire**,
une catégorie d'incident facultative (unique) et des étapes ordonnées. Définies dans Paramètres > Réponse aux incidents.

**Fichiers** : `models.py` · `schemas.py` (`PlaybookWriteRequest` = playbook complet) · `repository.py` · `service.py` · `router.py`.

**Règles clés** : modifier remplace la liste d'étapes ; une étape renvoyée avec son `id` est conservée (et son suivi
dans les incidents aussi). Supprimer un playbook le détache des incidents (`SET NULL`). Tout est tracé dans le journal.

**Fonctions publiques** (utilisées par `incidents`) : `find_playbook_id_for_category`, `fetch_playbook_detail`,
`fetch_playbook_details_by_ids`.

**Tester** : `python -m pytest tests/features/playbooks`.

**Doc** : [docs/technical/playbooks.md](../../../docs/technical/playbooks.md). Suivre [AGENTS.md](../../../AGENTS.md).
