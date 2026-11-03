"""Schémas Pydantic de la fonctionnalité `raw_syslog_feed` (logs bruts reçus, avant tout filtre)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.core.criticality import CriticalityLevel

MAXIMUM_MESSAGES_PER_FEED_PAGE = 500
MAXIMUM_SEARCH_TEXT_LENGTH = 200


class CollectionOutcomeFilter(StrEnum):
    """Filtre « que fera la collecte de ce log ? »."""

    ALL = "tous"
    STORED = "enregistres"
    DISCARDED = "ecartes"


class RawSyslogFeedFilters(BaseModel):
    """Filtres du flux. `apres` : numéro du dernier message déjà affiché (0 = depuis le plus ancien gardé)."""

    criticite: CriticalityLevel | None = None
    enregistrement: CollectionOutcomeFilter = CollectionOutcomeFilter.ALL
    # Recherche sans distinction de casse dans le texte brut du message (adresse IP, nom d'équipement, logid...).
    recherche: str | None = Field(default=None, max_length=MAXIMUM_SEARCH_TEXT_LENGTH)
    apres: int = Field(default=0, ge=0)
    limite: int = Field(default=200, ge=1, le=MAXIMUM_MESSAGES_PER_FEED_PAGE)


class RawSyslogMessageRead(BaseModel):
    """Un message reçu, tel quel, avec ce que la collecte en fera."""

    numero: int
    recu_le: datetime
    adresse_emetteur: str
    protocole: str
    texte_brut: str
    est_lisible: bool
    # Champs Fortinet du message, dans leur ordre d'arrivée (sans les métadonnées de réception).
    champs: dict[str, str]
    niveau_source: str | None
    criticite_source: CriticalityLevel | None
    type: str | None
    equipement: str | None
    resume: str | None
    est_enregistre_par_la_collecte: bool
    # Pourquoi le log n'est pas enregistré (sous le seuil, illisible, sévérité inconnue...), sinon None.
    motif_non_enregistrement: str | None


class SeverityLevelDistributionRead(BaseModel):
    """Nombre de messages lisibles reçus pour une valeur brute du niveau (`severity`, sinon `level`)."""

    niveau_source: str
    nombre: int
    pourcentage: float
    criticite_source: CriticalityLevel | None
    est_enregistre_par_la_collecte: bool


class RawSyslogFeedStatisticsRead(BaseModel):
    """Bilan depuis le démarrage de l'écoute : explique l'écart entre logs reçus et logs enregistrés."""

    est_en_mode_demo: bool
    est_a_l_ecoute: bool
    severite_minimale: CriticalityLevel
    nb_messages_lisibles: int
    nb_messages_enregistrables: int
    nb_messages_ecartes_par_le_seuil: int
    nb_messages_illisibles: int
    nb_messages_emetteur_refuse: int
    nb_messages_perdus_file_pleine: int
    nb_datagrammes_udp_perdus_par_le_systeme: int | None
    repartition_par_niveau: list[SeverityLevelDistributionRead]
    nb_messages_gardes_pour_affichage: int
    capacite_affichage: int


class RawSyslogFeedRead(BaseModel):
    """Messages correspondant aux filtres (plus récent d'abord) et numéro du dernier message reçu, à renvoyer dans
    `apres` à l'appel suivant pour ne recevoir que les nouveaux."""

    messages: list[RawSyslogMessageRead]
    dernier_numero: int
    statistiques: RawSyslogFeedStatisticsRead
