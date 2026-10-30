"""Erreurs de l'intégration FortiAnalyzer.

Leurs messages finissent dans l'historique des imports (`executions_import.erreur`) : ils ne doivent JAMAIS contenir
de secret. Ils citent seulement l'opération et la cause (réglage manquant, port occupé...).
"""


class FortiAnalyzerError(Exception):
    """Classe parente : toute erreur de récupération des alertes."""


class FortiAnalyzerConfigurationError(FortiAnalyzerError):
    """La configuration (.env) est incomplète ou incohérente."""


class SyslogReceptionError(FortiAnalyzerError):
    """La réception syslog n'est pas active (port déjà utilisé, droits insuffisants, application pas démarrée...)."""
