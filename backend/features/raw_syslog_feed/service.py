"""Flux des logs bruts : ce que FortiAnalyzer envoie réellement, AVANT le filtre de sévérité de la collecte.

Pourquoi : la base ne contient que les logs au-dessus de `LOG_COLLECTION_MINIMUM_CRITICALITY`, ce qui crée un grand
écart avec la vue de FortiAnalyzer. Cette fonctionnalité montre les messages tels qu'ils arrivent et la répartition
par niveau, pour vérifier qu'aucun log ne manque et comprendre ce qui est écarté.

Règles :
- source : la mémoire bornée du récepteur syslog (`SYSLOG_RECENT_MESSAGES_KEPT_FOR_DISPLAY` derniers messages). Rien
  n'est lu ni écrit en base, et la collecte n'est pas affectée (la mémoire d'affichage est distincte de sa file) ;
- « enregistré ou écarté » est calculé avec les règles de la collecte elle-même
  (`log_collection.service.evaluate_raw_log_against_collection_threshold`) : l'affichage ne peut pas diverger ;
- en mode démonstration, il n'y a pas de réception syslog : le flux est vide.

Fonctions publiques : `read_raw_syslog_feed`.
"""

from backend.core.criticality import CriticalityLevel
from backend.core.settings import ApplicationSettings
from backend.features.log_collection import service as log_collection_service
from backend.features.raw_syslog_feed.schemas import (
    CollectionOutcomeFilter,
    RawSyslogFeedFilters,
    RawSyslogFeedRead,
    RawSyslogFeedStatisticsRead,
    RawSyslogMessageRead,
    SeverityLevelDistributionRead,
)
from backend.integrations.fortianalyzer.fortianalyzer_log_source import SYSLOG_RECEPTION_METADATA_FIELD
from backend.integrations.fortianalyzer.fortianalyzer_syslog_receiver import (
    MISSING_SEVERITY_LABEL,
    RecentlyReceivedSyslogMessage,
    read_severity_label,
)
from backend.integrations.fortianalyzer.log_source_selection import (
    count_shared_udp_datagrams_lost_by_system,
    read_shared_recent_syslog_messages,
    read_shared_syslog_reception_statistics,
)

BELOW_THRESHOLD_REASON = "sous la sévérité minimale enregistrée"
UNREADABLE_MESSAGE_REASON = "message illisible (aucune paire clé=valeur)"
# Champs Fortinet essayés dans l'ordre pour résumer un log en une ligne.
SUMMARY_FIELDS = ("logdesc", "msg", "attack", "virus", "action")


def read_raw_syslog_feed(settings: ApplicationSettings, filters: RawSyslogFeedFilters) -> RawSyslogFeedRead:
    """Retourne les messages reçus après `filters.apres` qui correspondent aux filtres (au plus `filters.limite`, les
    plus récents d'abord), le numéro du dernier message reçu et le bilan par niveau. Ne lève pas."""
    recent_messages = [] if settings.app_is_in_demo else read_shared_recent_syslog_messages(filters.apres)
    search_text = (filters.recherche or "").strip().lower()
    matching_messages: list[RawSyslogMessageRead] = []
    for recent_message in reversed(recent_messages):
        if search_text and search_text not in recent_message.raw_text.lower():
            continue
        message_read = _describe_received_message(recent_message, settings)
        if not _matches_filters(message_read, filters):
            continue
        matching_messages.append(message_read)
        if len(matching_messages) >= filters.limite:
            break
    return RawSyslogFeedRead(
        messages=matching_messages,
        dernier_numero=recent_messages[-1].sequence_number if recent_messages else filters.apres,
        statistiques=read_raw_syslog_statistics(settings),
    )


def _describe_received_message(
    recent_message: RecentlyReceivedSyslogMessage, settings: ApplicationSettings
) -> RawSyslogMessageRead:
    parsed_log = recent_message.parsed_log
    if parsed_log is None:
        return RawSyslogMessageRead(
            numero=recent_message.sequence_number,
            recu_le=recent_message.received_at,
            adresse_emetteur=recent_message.sender_address,
            protocole=recent_message.protocol,
            texte_brut=recent_message.raw_text,
            est_lisible=False,
            champs={},
            niveau_source=None,
            criticite_source=None,
            type=None,
            equipement=None,
            resume=None,
            est_enregistre_par_la_collecte=False,
            motif_non_enregistrement=UNREADABLE_MESSAGE_REASON,
        )
    evaluation = log_collection_service.evaluate_raw_log_against_collection_threshold(parsed_log, settings)
    if evaluation.invalid_reason:
        non_storage_reason = evaluation.invalid_reason
    elif not evaluation.is_stored_by_collection:
        non_storage_reason = BELOW_THRESHOLD_REASON
    else:
        non_storage_reason = None
    severity_label = read_severity_label(parsed_log)
    return RawSyslogMessageRead(
        numero=recent_message.sequence_number,
        recu_le=recent_message.received_at,
        adresse_emetteur=recent_message.sender_address,
        protocole=recent_message.protocol,
        texte_brut=recent_message.raw_text,
        est_lisible=True,
        champs={key: str(value) for key, value in parsed_log.items() if key != SYSLOG_RECEPTION_METADATA_FIELD},
        niveau_source=None if severity_label == MISSING_SEVERITY_LABEL else severity_label,
        criticite_source=evaluation.criticite_source,
        type=evaluation.type,
        equipement=_read_text_field(parsed_log, "devname"),
        resume=next((_read_text_field(parsed_log, field) for field in SUMMARY_FIELDS if parsed_log.get(field)), None),
        est_enregistre_par_la_collecte=evaluation.is_stored_by_collection,
        motif_non_enregistrement=non_storage_reason,
    )


def _matches_filters(message_read: RawSyslogMessageRead, filters: RawSyslogFeedFilters) -> bool:
    if filters.criticite is not None and message_read.criticite_source != filters.criticite:
        return False
    if filters.enregistrement == CollectionOutcomeFilter.STORED:
        return message_read.est_enregistre_par_la_collecte
    if filters.enregistrement == CollectionOutcomeFilter.DISCARDED:
        return not message_read.est_enregistre_par_la_collecte
    return True


def read_raw_syslog_statistics(settings: ApplicationSettings) -> RawSyslogFeedStatisticsRead:
    """Retourne les compteurs depuis le démarrage de l'écoute, sans charger de messages ni écrire en base."""
    reception_statistics = None if settings.app_is_in_demo else read_shared_syslog_reception_statistics()
    counts_by_severity_label = reception_statistics.accepted_message_count_by_severity_label if reception_statistics else {}
    readable_message_count = sum(counts_by_severity_label.values())
    distribution = []
    for severity_label, message_count in sorted(counts_by_severity_label.items(), key=lambda item: -item[1]):
        # Même règle que la collecte, appliquée à un log réduit à son niveau.
        evaluation = log_collection_service.evaluate_raw_log_against_collection_threshold(
            {} if severity_label == MISSING_SEVERITY_LABEL else {"level": severity_label}, settings
        )
        distribution.append(
            SeverityLevelDistributionRead(
                niveau_source=severity_label,
                nombre=message_count,
                pourcentage=round(100 * message_count / readable_message_count, 2) if readable_message_count else 0,
                criticite_source=evaluation.criticite_source,
                est_enregistre_par_la_collecte=evaluation.is_stored_by_collection,
            )
        )
    storable_message_count = sum(level.nombre for level in distribution if level.est_enregistre_par_la_collecte)
    return RawSyslogFeedStatisticsRead(
        est_en_mode_demo=settings.app_is_in_demo,
        est_a_l_ecoute=bool(reception_statistics and reception_statistics.is_listening),
        severite_minimale=CriticalityLevel(settings.log_collection_minimum_criticality),
        nb_messages_lisibles=readable_message_count,
        nb_messages_enregistrables=storable_message_count,
        nb_messages_ecartes_par_le_seuil=readable_message_count - storable_message_count,
        nb_messages_illisibles=reception_statistics.unreadable_message_count if reception_statistics else 0,
        nb_messages_emetteur_refuse=reception_statistics.rejected_sender_message_count if reception_statistics else 0,
        nb_messages_perdus_file_pleine=(
            reception_statistics.dropped_because_queue_full_count if reception_statistics else 0
        ),
        nb_datagrammes_udp_perdus_par_le_systeme=(
            None if settings.app_is_in_demo else count_shared_udp_datagrams_lost_by_system()
        ),
        repartition_par_niveau=distribution,
        nb_messages_gardes_pour_affichage=len(read_shared_recent_syslog_messages()) if reception_statistics else 0,
        capacite_affichage=settings.syslog_recent_messages_kept_for_display,
    )


def _read_text_field(parsed_log: dict, field_name: str) -> str | None:
    field_value = str(parsed_log.get(field_name) or "").strip()
    return field_value or None
