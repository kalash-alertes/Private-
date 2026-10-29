"""Nettoyage des messages d'erreur avant leur enregistrement dans `executions_import.erreur`.

Pourquoi : le message d'une exception réseau peut contenir une URL avec identifiants, un en-tête Authorization
ou un jeton passé en paramètre. Ce module masque les motifs connus et tronque le texte.

Limite assumée : c'est un filet de sécurité, pas une garantie. L'appelant (le futur collecteur) reste responsable
de ne jamais construire de message contenant un secret.
"""

import re

MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH = 2000
REDACTED_VALUE_PLACEHOLDER = "***"

# Chaque motif capture un préfixe (conservé) suivi de la valeur sensible (masquée).
SENSITIVE_VALUE_PATTERNS = (
    # https://utilisateur:motdepasse@hote -> https://***@hote
    re.compile(r"(?P<prefix>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+(?=@)"),
    # Authorization: Bearer xxx / Basic xxx
    re.compile(r"(?P<prefix>\bauthorization\b\s*[:=]\s*(?:bearer|basic|token)?\s*)[^\s,;'\"]+", re.IGNORECASE),
    re.compile(r"(?P<prefix>\bbearer\s+)[^\s,;'\"]+", re.IGNORECASE),
    # password=..., token: ..., api_key=..., "session": "..." (formes clé/valeur et JSON)
    re.compile(
        r"(?P<prefix>[\"']?\b(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?token|session(?:id)?)\b"
        r"[\"']?\s*[:=]\s*[\"']?)[^\s,;&'\"}]+",
        re.IGNORECASE,
    ),
)


def sanitize_import_error_message(raw_error_message: str) -> str:
    """Masque les secrets reconnaissables et tronque le message. Retourne le message nettoyé (jamais vide)."""
    sanitized_message = raw_error_message
    for sensitive_value_pattern in SENSITIVE_VALUE_PATTERNS:
        sanitized_message = sensitive_value_pattern.sub(
            lambda match: f"{match.group('prefix')}{REDACTED_VALUE_PLACEHOLDER}", sanitized_message
        )
    sanitized_message = sanitized_message.strip()
    if len(sanitized_message) > MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH:
        sanitized_message = sanitized_message[: MAXIMUM_IMPORT_ERROR_MESSAGE_LENGTH - 15].rstrip() + " [...tronqué]"
    return sanitized_message or "Erreur sans message"


def build_import_error_message_from_exception(exception: BaseException) -> str:
    """Construit un message exploitable (`TypeException: message`) à partir d'une exception, déjà nettoyé."""
    exception_message = str(exception).strip()
    readable_message = f"{type(exception).__name__}: {exception_message}" if exception_message else type(exception).__name__
    return sanitize_import_error_message(readable_message)
