# Fonctionnalité `incident_response_settings` — délais et escalade

Code : `backend/features/incident_response_settings/`. Table : `delais_reponse_incidents`.
Interface : Paramètres > Réponse aux incidents (`/parametres/reponse-incidents`).

## Données

Une ligne par criticité (UNIQUE), créée par la migration 0003 avec des valeurs **par défaut à ajuster** :
critique 60 min, haute 4 h, moyenne 24 h, faible 72 h, information 7 j ; escalade désactivée partout.
Colonnes : `delai_traitement_minutes` (> 0), `escalade_automatique_activee`, `escalader_vers` (texte libre, NULL ou non
vide), `updated_at`. L'API ne crée ni ne supprime de ligne.

## Routes HTTP (API)

| Méthode | Route | Corps | Réponse |
|---|---|---|---|
| GET | `/api/parametres/reponse-incidents/delais` | — | règles, de critique à information |
| PUT | `/api/parametres/reponse-incidents/delais/{criticite}` | `{delai_traitement_minutes (1–525 600), escalade_automatique_activee, escalader_vers?}` | règle ; 422 |

Une modification effective est tracée (`parametres_modifies`, valeurs avant/après) ; une demande identique ne trace rien.
Dans l'interface, le délai est saisi avec une unité (minutes, heures, jours) convertie en minutes.

## Date limite et délai dépassé (calculés par `incidents/incident_views.py`)

- `date_limite_traitement` = `incidents.created_at` + délai de la **criticité actuelle**. Calculée, jamais stockée :
  changer un délai ou réévaluer la criticité déplace la date limite. Choix assumé (la règle en vigueur s'applique
  partout). Le délai court depuis la **création de l'incident**, pas depuis l'heure de l'alerte.
- `delai_depasse` : incident ouvert ⇒ maintenant > date limite ; incident traité ⇒ `traite_le` > date limite ;
  `null` si aucune règle.

## Escalade automatique (`incidents/automatic_escalation.py`)

Éligible : incident **ouvert**, `escalade_le IS NULL`, règle de sa criticité active, date limite dépassée.
Effet : `escalade_le = now()`, réattribution à `escalader_vers` si renseigné, événement `incident_escalade`
(acteur NULL = système). Une seule escalade par incident ; ni statut ni criticité modifiés ; aucune action sur
l'infrastructure.

Déclenchement : `POST /api/incidents/escalade-automatique`, bouton « Lancer l'escalade maintenant » de l'interface,
et boucle de fond si `AUTOMATIC_ESCALATION_INTERVAL_SECONDS` > 0 (300 dans `docker-compose.yml` ; 0 par défaut et en
test). Concurrence : `SELECT ... FOR UPDATE SKIP LOCKED` ; PostgreSQL réévalue `escalade_le IS NULL` après
verrouillage, deux exécutions simultanées n'escaladent donc jamais deux fois. Une erreur dans la boucle est
journalisée et la boucle reprend au tour suivant.

Point ouvert : avec plusieurs instances du backend, chacune lance sa boucle (sans doublon grâce au verrou, mais
inutilement) ; prévoir une seule instance « planificateur » si l'application est un jour répliquée.
