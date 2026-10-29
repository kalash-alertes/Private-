"""Erreurs de l'intégration FortiAnalyzer.

Leurs messages finissent dans l'historique des imports (`executions_import.erreur`) : ils ne doivent JAMAIS contenir
de mot de passe, de jeton ni d'identifiant de session. Ils citent seulement l'opération et le code renvoyé.
"""


class FortiAnalyzerError(Exception):
    """Classe parente : toute erreur de récupération des alertes."""


class FortiAnalyzerConfigurationError(FortiAnalyzerError):
    """La configuration (.env) est incomplète ou incohérente : aucune connexion n'a été tentée."""


class FortiAnalyzerConnectionError(FortiAnalyzerError):
    """FortiAnalyzer est injoignable ou répond hors protocole (réseau, TLS, délai dépassé, HTTP ≠ 200, JSON invalide)."""


class FortiAnalyzerApiError(FortiAnalyzerError):
    """FortiAnalyzer a répondu, mais avec un code d'erreur (identifiants refusés, ADOM inconnu, droits insuffisants...)."""
