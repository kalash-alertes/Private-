"""Messages de confirmation affichés après une action (bandeau « toast »).

Après un POST réussi, la page redirige vers `...?notice=<clé>` (modèle POST → redirection → GET : recharger la page ne
rejoue pas l'action). Seules les clés connues ci-dessous sont affichées : aucun texte venant de l'URL n'est recopié
dans la page, ce qui empêche d'y injecter un faux message.
"""

PAGE_NOTICE_MESSAGES_BY_KEY = {
    "incident_cree": "Incident créé.",
    "incident_modifie": "Incident mis à jour.",
    "etape_mise_a_jour": "Avancement du playbook mis à jour.",
    "playbook_cree": "Playbook créé.",
    "playbook_modifie": "Playbook enregistré.",
    "playbook_supprime": "Playbook supprimé.",
    "delai_modifie": "Délai de réponse enregistré.",
    "escalade_executee": "Escalade automatique exécutée.",
    "collecte_executee": "Collecte terminée : voir son résultat en tête de l'historique.",
}


def find_page_notice_message(notice_key: str | None) -> str | None:
    """Retourne le message de cette clé, ou None si la clé est absente ou inconnue."""
    return PAGE_NOTICE_MESSAGES_BY_KEY.get(notice_key) if notice_key else None
