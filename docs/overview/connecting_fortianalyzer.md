# Brancher l'application sur FortiAnalyzer

L'application peut lire ses alertes à deux endroits, au choix, grâce à une seule ligne du fichier `.env` :

| `APP_IS_IN_DEMO=` | D'où viennent les alertes |
|---|---|
| `true` (par défaut) | **Démonstration** : quelques alertes **inventées** à chaque collecte. Aucune connexion à FortiAnalyzer. Un badge « DÉMO » est affiché en haut de l'écran. |
| `false` | **Le vrai FortiAnalyzer**, avec l'adresse et les identifiants indiqués dans le `.env`. |

Dans les deux cas, la suite est identique : les alertes arrivent dans **Alertes**, chaque passage est inscrit dans
**Journaux**, et on crée les incidents comme d'habitude.

---

## 1. Préparer FortiAnalyzer (à faire par l'administrateur FortiAnalyzer)

1. Créer un **compte dédié à l'application**, avec des droits en **lecture seule** sur les logs : l'application ne
   fait que lire, elle n'envoie jamais d'ordre à FortiAnalyzer.
2. Autoriser ce compte à utiliser l'**API JSON** (option « JSON API Access » en lecture).
3. Au choix :
   - **jeton API** (FortiAnalyzer 7.2.2 et plus, recommandé) : générer un jeton pour ce compte ;
   - **sinon**, noter l'identifiant et le mot de passe du compte.
4. Noter : l'**adresse** de FortiAnalyzer (ex. `https://192.168.1.50`), l'**ADOM** à lire (`root` si les ADOM ne sont
   pas activés) et le **fuseau horaire** de FortiAnalyzer.
5. Si le certificat HTTPS de FortiAnalyzer est **auto-signé** : récupérer le certificat de l'autorité (fichier `.pem`).

## 2. Remplir le fichier `.env`

Ouvrir `F:\shared_folder\Intelligentsia_SOC\.env` (jamais envoyé sur GitHub) et remplir la partie FortiAnalyzer :

```ini
APP_IS_IN_DEMO=false

FORTIANALYZER_BASE_URL=https://192.168.1.50
FORTIANALYZER_ADOM=root
FORTIANALYZER_TIMEZONE=Europe/Paris

# Soit un jeton API…
FORTIANALYZER_API_TOKEN=le_jeton
# …soit identifiant + mot de passe (laisser le jeton vide)
FORTIANALYZER_USERNAME=
FORTIANALYZER_PASSWORD=
```

Réglages utiles (déjà remplis avec des valeurs par défaut) :

| Variable | Rôle | Défaut |
|---|---|---|
| `FORTIANALYZER_LOG_TYPES` | Types de logs lus : `event` (système), `attack` (IPS), `virus`, `webfilter`… | `event,attack` |
| `LOG_COLLECTION_MINIMUM_CRITICALITY` | Sévérité minimale gardée (`information` → `critique`) | `haute` |
| `LOG_COLLECTION_INTERVAL_SECONDS` | Collecte automatique toutes les N secondes (0 = manuelle) | `300` (5 min) |
| `LOG_COLLECTION_INITIAL_LOOKBACK_HOURS` | Historique récupéré à la toute première collecte | `24` |
| `FORTIANALYZER_DEVICE_IDENTIFIER` | Équipements lus | `All_FortiGate` |
| `FORTIANALYZER_VERIFY_TLS` / `FORTIANALYZER_CA_BUNDLE_PATH` | Vérification du certificat HTTPS | `true` / vide |

**Certificat auto-signé** : copier le fichier dans le dossier `certificates\` du projet, puis :
`FORTIANALYZER_CA_BUNDLE_PATH=/application/certificates/nom_du_fichier.pem`.
(Mettre `FORTIANALYZER_VERIFY_TLS=false` marche aussi, mais la connexion et le mot de passe pourraient alors être
interceptés : à réserver à un essai rapide.)

## 3. Appliquer et vérifier

```powershell
wsl docker compose up -d
```

(Cette commande recrée l'application avec le nouveau `.env` ; pas besoin de reconstruire l'image.)

Puis ouvrir **http://localhost:8000/journaux** :

- l'encadré du haut doit afficher **FortiAnalyzer**, l'adresse et l'ADOM, avec le badge « Données réelles » ;
- s'il manque un réglage, un bandeau rouge dit lequel ;
- cliquer sur **« Lancer une collecte maintenant »** : une ligne s'ajoute à l'historique.
  - **Réussie** : la connexion fonctionne ; les alertes sont dans **Alertes**.
  - **Échouée** : le motif est dans la colonne Erreur (passer la souris dessus pour le lire en entier).

Les messages de l'application sont aussi visibles avec `wsl docker compose logs -f backend`.

## 4. En cas d'échec

| Motif affiché | Que faire |
|---|---|
| `configuration incomplète … FORTIANALYZER_…` | Remplir la variable citée dans le `.env`, puis `wsl docker compose up -d`. |
| `FortiAnalyzer injoignable (ConnectError)` | Vérifier l'adresse et le port ; depuis le poste, tester l'ouverture de l'adresse dans un navigateur. Le conteneur passe par le réseau de WSL : FortiAnalyzer doit être joignable depuis le poste. |
| `injoignable (ConnectError)` juste après un changement de certificat, ou erreur SSL | Certificat non reconnu : voir « Certificat auto-signé » ci-dessus. |
| `délai dépassé` | FortiAnalyzer lent ou période trop longue : augmenter `FORTIANALYZER_REQUEST_TIMEOUT_SECONDS`. |
| `erreur FortiAnalyzer -11` (ou autre code) à la connexion | Identifiants refusés ou compte sans accès API. |
| `erreur FortiAnalyzer …` à la recherche | ADOM inconnu, droits insuffisants sur les logs, ou type de log invalide dans `FORTIANALYZER_LOG_TYPES`. |
| `plus de 50000 logs sur la période` | Réduire `LOG_COLLECTION_INITIAL_LOOKBACK_HOURS`, relever la sévérité minimale ou ajouter un filtre. |
| Collecte **partielle**, « log(s) invalide(s) » | Certains logs n'ont pas de sévérité ou de date lisible : transmettre un exemple (anonymisé) pour adapter la conversion. |

## 5. À savoir

- Une collecte qui échoue est **rejouée** à la suivante sur la même période : rien n'est perdu.
- Une même alerte n'est **jamais enregistrée deux fois**, même si deux collectes se chevauchent.
- La sévérité d'origine de FortiAnalyzer est conservée telle quelle ; elle peut être réévaluée dans l'incident.
- Le mot de passe et le jeton ne sont **jamais affichés** dans l'interface, ni écrits dans les journaux.
- **Première connexion réelle à valider ensemble** : le client a été écrit d'après la documentation publique de
  Fortinet et testé contre un faux serveur, pas encore contre votre FortiAnalyzer. Les noms de champs peuvent varier
  selon la version : si la première collecte échoue ou classe mal les sévérités, partager le motif de l'erreur
  (et un exemple de log anonymisé).
- Revenir à la démonstration : `APP_IS_IN_DEMO=true`, puis `wsl docker compose up -d`. Les alertes réelles déjà
  enregistrées restent en base.
