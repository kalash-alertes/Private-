# certificates/

Si FortiAnalyzer utilise un certificat HTTPS **auto-signé** (cas fréquent), déposer ici le certificat de l'autorité
(fichier `.pem`), puis dans le `.env` :

```
FORTIANALYZER_CA_BUNDLE_PATH=/application/certificates/<nom_du_fichier>.pem
```

Ce dossier est monté en lecture seule dans le conteneur. Les fichiers de certificat ne sont pas commités
(`.gitignore`). Désactiver la vérification (`FORTIANALYZER_VERIFY_TLS=false`) est possible mais déconseillé : la
connexion (et le mot de passe) pourrait alors être interceptée.
