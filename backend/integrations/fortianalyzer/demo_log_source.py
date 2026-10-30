"""Source de DÉMONSTRATION : invente quelques logs au format FortiAnalyzer à chaque collecte (APP_IS_IN_DEMO=true).

Les logs ressemblent à ceux de FortiAnalyzer (champs `itime`, `level`, `type`, `subtype`, `msg`...) pour que toute la
chaîne (conversion, déduplication, historique des imports, incidents) fonctionne comme en réel. Ils sont marqués
`demonstration: true` et leur équipement s'appelle `DEMO-FGT-...` : ils ne peuvent pas être confondus avec de vrais logs.
"""

import random
from datetime import datetime
from uuid import uuid4

from backend.integrations.fortianalyzer.critical_log_source import RawFortiAnalyzerLog

DEMO_SOURCE_DESCRIPTION = "Démonstration (alertes inventées, aucune connexion à FortiAnalyzer)"

# (type, sous-type, champ de sévérité, valeur, message) : un échantillon varié de situations typiques.
DEMO_LOG_TEMPLATES = [
    ("utm", "ips", "severity", "critical", "Tentative d'exploitation détectée (démonstration)"),
    ("utm", "ips", "severity", "high", "Signature d'attaque réseau reconnue (démonstration)"),
    ("utm", "virus", "level", "critical", "Fichier malveillant bloqué (démonstration)"),
    ("event", "system", "level", "alert", "Échecs de connexion administrateur répétés (démonstration)"),
    ("event", "vpn", "level", "error", "Tunnel VPN tombé de façon inattendue (démonstration)"),
    ("utm", "webfilter", "level", "warning", "Accès à un site classé à risque (démonstration)"),
    ("event", "system", "level", "notice", "Configuration modifiée (démonstration)"),
]
MAXIMUM_DEMO_LOGS_PER_COLLECTION = 4


class DemoCriticalLogSource:
    """Respecte le contrat `CriticalLogSource`. `random_generator` permet des tests reproductibles."""

    def __init__(self, random_generator: random.Random | None = None) -> None:
        self._random = random_generator or random.Random()

    @property
    def source_description(self) -> str:
        return DEMO_SOURCE_DESCRIPTION

    def take_new_logs(self, period_start: datetime, period_end: datetime) -> list[RawFortiAnalyzerLog]:
        """Invente de 1 à 4 logs datés dans la période (certains en dessous du seuil de sévérité, comme en réel)."""
        start_timestamp, end_timestamp = int(period_start.timestamp()), int(period_end.timestamp())
        demo_logs = []
        for _ in range(self._random.randint(1, MAXIMUM_DEMO_LOGS_PER_COLLECTION)):
            log_type, log_subtype, severity_field, severity_value, message = self._random.choice(DEMO_LOG_TEMPLATES)
            device_number = self._random.randint(1, 3)
            demo_logs.append(
                {
                    "itime": self._random.randint(start_timestamp, max(start_timestamp, end_timestamp)),
                    "logid": f"DEMO{self._random.randint(1000, 9999)}",
                    "type": log_type,
                    "subtype": log_subtype,
                    severity_field: severity_value,
                    "devid": f"DEMO-FGT-{device_number:02d}",
                    "devname": f"DEMO-FortiGate-{device_number:02d}",
                    "srcip": f"192.0.2.{self._random.randint(1, 254)}",  # plage réservée à la documentation
                    "dstip": f"198.51.100.{self._random.randint(1, 254)}",  # plage réservée à la documentation
                    "msg": message,
                    # Rend chaque log unique (sinon deux logs identiques seraient dédupliqués).
                    "demo_identifier": str(uuid4()),
                    "demonstration": True,
                }
            )
        return demo_logs
