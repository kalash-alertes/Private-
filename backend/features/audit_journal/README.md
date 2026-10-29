# Feature `audit_journal`

**Rôle** : journal des événements du système (table `journal_audit`), en ajout seul. Consultable dans
Paramètres > Journal d'audit et via `GET /api/parametres/journal-audit`.

**Fichiers** : `models.py` (types d'événements) · `schemas.py` · `repository.py` · `service.py` · `router.py` (lecture seule).

**Utiliser depuis une autre feature** : `service.record_audit_event(session, NewAuditEventData(...))` ajoute l'événement
à la transaction de l'appelant **sans commit** : il est enregistré seulement si l'action l'est aussi.

**Connexions** : les types `connexion_reussie` / `connexion_echouee` / `deconnexion` existent ; ils seront écrits par la
future authentification (aucune connexion n'existe encore). Ne jamais y mettre un mot de passe.

**Tester** : `python -m pytest tests/features/audit_journal`.

**Doc** : [docs/technical/audit_journal.md](../../../docs/technical/audit_journal.md). Suivre [AGENTS.md](../../../AGENTS.md).
