# Playbooks (un fichier JSON lisible par playbook)

Ce dossier est la référence des playbooks ; la base de données en est l'index. Format et règles :
[docs/technical/playbooks.md](../../docs/technical/playbooks.md).

- Créer, modifier, supprimer dans l'interface (page Playbooks) écrit le fichier correspondant.
- Ajouter ou modifier un fichier à la main : il est enregistré au démarrage de l'application, ou avec le bouton
  « Synchroniser avec les fichiers » (ou `python -m scripts.synchronize_playbook_files`). Un nouveau fichier peut
  omettre les `id` : ils sont ajoutés à la synchronisation.
- Un texte sur plusieurs lignes s'écrit en liste de lignes. L'ordre des étapes est celui de la liste. Garder l'`id`
  d'une étape conserve son suivi (« réalisée ») dans les incidents.
- La `source` est obligatoire : référence vérifiable (lien, version, licence).

Fiches IRM : CERT Société Générale, version française CERT aDvens (https://github.com/cert-advens/IRM), licence
CC BY 3.0 — régénérer avec `python -m scripts.build_reference_playbooks_from_cert_irm` (PyMuPDF requis). Force brute :
MITRE ATT&CK T1110 (https://attack.mitre.org/techniques/T1110/) et NIST SP 800-61 Rév. 2.
