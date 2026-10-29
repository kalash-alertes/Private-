# Fonctionnalité `audit_journal` — journal d'audit

Code : `backend/features/audit_journal/`. Table : `journal_audit`. Interface : Paramètres > Journal d'audit.

## Données

`date_evenement` (horloge DB), `type_evenement` (CHECK), `acteur` (NULL = système), `type_ressource` +
`identifiant_ressource` (ex. `incident` + id, pour ouvrir l'élément), `description` (non vide), `details` (JSON),
`adresse_ip`. Index sur la date et le type. **Ajout seul** : aucune route de modification ou de suppression.

Types : `connexion_reussie`, `connexion_echouee`, `deconnexion` (prêts pour l'authentification à venir),
`incident_cree`, `incident_modifie`, `incident_escalade`, `playbook_cree`, `playbook_modifie`, `playbook_supprime`,
`parametres_modifies`. Ajouter un type = modifier l'enum **et** écrire une migration (contrainte CHECK).

## Écriture

`service.record_audit_event(session, NewAuditEventData)` ajoute l'événement à la session de l'appelant **sans commit** :
l'événement et la modification décrite sont validés ou annulés ensemble. Écrivent aujourd'hui : `incidents`
(création, chaque changement effectif, étapes, escalade), `playbooks`, `incident_response_settings`.
Ne jamais y mettre de secret, de mot de passe ni de donnée brute de log.

## Lecture

`GET /api/parametres/journal-audit?type_evenement=&acteur=&type_ressource=&identifiant_ressource=&date_evenement_min=&date_evenement_max=&limit=&offset=`
(bornes incluses, dates avec fuseau, plage inversée ⇒ 422). Tri : date décroissante puis id. Des événements de la
même seconde (précision de SQLite en test) n'ont pas d'ordre garanti entre eux.

## Limite actuelle

Sans authentification, `acteur` reste vide pour les actions faites depuis l'interface : l'application ne sait pas
encore qui agit (sauf « réalisée par » d'une étape, saisi librement). Les connexions réussies/échouées apparaîtront
quand la connexion des utilisateurs existera.
