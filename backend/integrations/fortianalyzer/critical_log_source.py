"""Contrat commun à toutes les sources d'alertes (vrai FortiAnalyzer, démonstration, faux de test).

La collecte (`backend/features/log_collection`) ne connaît que ce contrat : elle ne sait pas si les logs viennent du
vrai FortiAnalyzer ou de la démonstration. C'est ce qui permet de basculer avec `APP_IS_IN_DEMO` sans toucher au reste.
"""

from datetime import datetime
from typing import Any, Protocol

# Un log tel que renvoyé par FortiAnalyzer : dictionnaire de champs (`itime`, `level`, `subtype`, `msg`...).
# Il est validé et converti par la collecte (log_collection/fortianalyzer_log_normalizer.py), pas ici.
RawFortiAnalyzerLog = dict[str, Any]


class CriticalLogSource(Protocol):
    """Une source capable de renvoyer les logs d'une période."""

    @property
    def source_description(self) -> str:
        """Description lisible de la source (sans secret), affichée dans l'interface et l'historique."""

    def fetch_logs_between(self, period_start: datetime, period_end: datetime) -> list[RawFortiAnalyzerLog]:
        """Retourne les logs dont la date est dans [period_start, period_end] (dates UTC avec fuseau).

        Lève une `FortiAnalyzerError` si la récupération échoue : la collecte enregistre alors un import « échoué ».
        """
