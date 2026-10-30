"""Contrat commun à toutes les sources d'alertes (réception syslog réelle, démonstration, faux de test).

La collecte (`backend/features/log_collection`) ne connaît que ce contrat : elle ne sait pas si les logs viennent du
vrai FortiAnalyzer ou de la démonstration. C'est ce qui permet de basculer avec `APP_IS_IN_DEMO` sans toucher au reste.
"""

from datetime import datetime
from typing import Any, Protocol

# Un log tel qu'envoyé par FortiAnalyzer : dictionnaire de champs (`eventtime`, `level`, `subtype`, `msg`...).
# Il est validé et converti par la collecte (log_collection/fortianalyzer_log_normalizer.py), pas ici.
RawFortiAnalyzerLog = dict[str, Any]

# Champ ajouté par l'application à chaque log reçu par syslog (émetteur, protocole, heure de réception). Il n'est PAS
# un champ FortiAnalyzer : il est exclu de l'empreinte de déduplication (sinon l'heure de réception la rendrait unique).
SYSLOG_RECEPTION_METADATA_FIELD = "reception_syslog"


class CriticalLogSource(Protocol):
    """Une source capable de remettre les logs arrivés depuis la collecte précédente."""

    @property
    def source_description(self) -> str:
        """Description lisible de la source (sans secret), affichée dans l'interface et l'historique."""

    def take_new_logs(self, period_start: datetime, period_end: datetime) -> list[RawFortiAnalyzerLog]:
        """Retourne (et retire de la source) les logs arrivés depuis la collecte précédente.

        `period_start` / `period_end` (UTC avec fuseau) sont les bornes de la collecte : la démonstration s'en sert
        pour dater ses logs ; la réception syslog les ignore (elle vide sa file d'attente).
        Lève une `FortiAnalyzerError` si la source est indisponible : la collecte enregistre alors un import « échoué ».
        """
