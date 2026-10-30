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


class SyslogReceptionStatisticsRead(BaseModel):
    """Compteurs de la réception syslog depuis le démarrage de l'application."""

    nb_logs_en_attente: int
    nb_messages_acceptes: int
    nb_messages_emetteur_refuse: int
    nb_messages_illisibles: int
    nb_messages_perdus_file_pleine: int


class LogCollectionConfigurationRead(BaseModel):
    """Configuration visible de la collecte et état de la réception syslog (aucun secret)."""

    est_en_mode_demo: bool
    source: str
    adresse_ecoute: str | None
    port_ecoute: int | None
    protocoles: list[str]
    # Vide = tous les émetteurs acceptés.
    emetteurs_autorises: list[str]
    est_a_l_ecoute: bool
    # Motif de l'échec du démarrage de l'écoute (port déjà utilisé...), sinon None.
    erreur_reception: str | None
    reception: SyslogReceptionStatisticsRead | None
    parametres_manquants: list[str]
    intervalle_collecte_secondes: float
    severite_minimale: str
