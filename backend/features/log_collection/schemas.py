"""Schémas Pydantic de la fonctionnalité `log_collection`."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.features.import_runs.models import ImportRunStatus


class LogCollectionResultRead(BaseModel):
    """Bilan d'une collecte (l'exécution correspondante est dans l'historique des imports).

    `nb_logs_lus_sur_la_source` = tous les logs renvoyés ; `nb_logs_sous_le_seuil` en sont écartés (filtre de
    sévérité) ; le reste = `nb_logs_recus` (valeur de l'historique des imports) = `nb_logs_inseres` (nouveaux)
    + `nb_logs_ignores` (déjà connus) + `nb_logs_invalides`.
    """

    import_run_id: UUID
    statut: ImportRunStatus
    source: str
    periode_debut: datetime
    periode_fin: datetime
    nb_logs_lus_sur_la_source: int
    nb_logs_recus: int
    nb_logs_inseres: int
    nb_logs_ignores: int
    nb_logs_sous_le_seuil: int
    nb_logs_invalides: int
    erreur: str | None


class LogCollectionConfigurationRead(BaseModel):
    """Configuration visible de la collecte (AUCUN secret : ni mot de passe, ni jeton)."""

    est_en_mode_demo: bool
    source: str
    adresse_fortianalyzer: str | None
    adom: str | None
    types_de_logs: list[str]
    authentification: str | None
    parametres_manquants: list[str]
    intervalle_collecte_secondes: float
    severite_minimale: str
