"""Nom du fichier JSON d'un playbook, dérivé de son nom (sans dépendance : utilisé aussi par les scripts outils).

« IRM-07 — Malware sous Windows » → `irm-07-malware-sous-windows.json` : minuscules, sans accents, mots séparés par
des tirets. Le fichier est retrouvé par l'`id` qu'il contient, pas par son nom : renommer un playbook renomme son
fichier sans casser le lien.
"""

import re
import unicodedata

PLAYBOOK_FILE_EXTENSION = ".json"
MAXIMUM_FILE_STEM_LENGTH = 80


def build_playbook_file_name(playbook_name: str) -> str:
    """Retourne `<nom-lisible>.json` (« playbook.json » si le nom ne contient aucune lettre ni chiffre)."""
    ascii_name = unicodedata.normalize("NFKD", playbook_name).encode("ascii", "ignore").decode("ascii")
    file_stem = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:MAXIMUM_FILE_STEM_LENGTH].strip("-")
    return (file_stem or "playbook") + PLAYBOOK_FILE_EXTENSION
