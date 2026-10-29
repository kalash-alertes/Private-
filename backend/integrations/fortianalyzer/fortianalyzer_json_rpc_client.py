"""Client de l'API JSON-RPC de FortiAnalyzer : récupère les logs d'une période.

Déroulé d'une récupération (`fetch_logs_between`) :
1. Authentification : jeton API dans l'en-tête `Authorization: Bearer` (FortiAnalyzer 7.2.2+), sinon connexion
   `exec /sys/login/user` (identifiant + mot de passe) qui renvoie un identifiant de session ;
2. pour chaque type de log configuré : lancement d'une recherche `add /logview/adom/<adom>/logsearch` (renvoie un
   `tid`), attente de la fin de la recherche, lecture des résultats page par page (`get .../logsearch/<tid>`), puis
   libération de la recherche (`delete`) ;
3. déconnexion (`exec /sys/logout`) si une session a été ouverte — même en cas d'erreur.

IMPORTANT — à vérifier sur le FortiAnalyzer de l'équipe : ce client suit l'API publique documentée par Fortinet
(LogView, `apiver` 3). Il n'a PAS encore été testé contre un vrai FortiAnalyzer ; les noms de champs, la syntaxe du
filtre et le fuseau des bornes peuvent varier selon la version. Les tests utilisent un faux serveur (httpx.MockTransport).

Sécurité : le mot de passe, le jeton et la session ne sont jamais placés dans un message d'erreur ni journalisés.
"""

import itertools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import SecretStr, ValidationError

from backend.integrations.fortianalyzer.critical_log_source import RawFortiAnalyzerLog
from backend.integrations.fortianalyzer.fortianalyzer_api_schemas import (
    JsonRpcResponse,
    LogSearchPageResult,
    LogSearchStartedResult,
)
from backend.integrations.fortianalyzer.fortianalyzer_errors import (
    FortiAnalyzerApiError,
    FortiAnalyzerConfigurationError,
    FortiAnalyzerConnectionError,
)

JSON_RPC_PATH = "/jsonrpc"
LOG_SEARCH_API_VERSION = 3
LOG_SEARCH_PAGE_SIZE = 500
# Une recherche FortiAnalyzer est asynchrone : on interroge son avancement toutes les secondes, 2 minutes au plus.
LOG_SEARCH_POLL_INTERVAL_SECONDS = 1.0
LOG_SEARCH_MAXIMUM_WAIT_SECONDS = 120.0
# Garde-fou : au-delà, la collecte s'arrête (période trop large ou filtre trop permissif) plutôt que saturer la base.
MAXIMUM_LOGS_PER_LOG_TYPE = 50_000
FORTIANALYZER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class FortiAnalyzerConnectionParameters:
    """Paramètres de connexion, construits depuis le .env (voir `log_source_selection.py`)."""

    base_url: str
    adom: str
    api_token: SecretStr = field(default_factory=lambda: SecretStr(""))
    username: str = ""
    password: SecretStr = field(default_factory=lambda: SecretStr(""))
    # True/False, ou chemin d'un fichier d'autorités de certification (CA).
    tls_verification: bool | str = True
    log_types: tuple[str, ...] = ("event",)
    device_identifier: str = "All_FortiGate"
    search_filter: str = ""
    timezone_name: str = "UTC"
    request_timeout_seconds: float = 30

    @property
    def uses_api_token(self) -> bool:
        return bool(self.api_token.get_secret_value())


class FortiAnalyzerJsonRpcClient:
    """Source d'alertes réelle (respecte le contrat `CriticalLogSource`)."""

    def __init__(
        self,
        connection_parameters: FortiAnalyzerConnectionParameters,
        http_transport: httpx.BaseTransport | None = None,
        wait_function: Callable[[float], None] = time.sleep,
    ) -> None:
        """`http_transport` et `wait_function` ne servent qu'aux tests (faux serveur, attente instantanée)."""
        self._connection_parameters = connection_parameters
        self._http_transport = http_transport
        self._wait = wait_function
        self._request_identifiers = itertools.count(1)
        try:
            self._fortianalyzer_timezone = ZoneInfo(connection_parameters.timezone_name)
        except Exception as timezone_error:
            raise FortiAnalyzerConfigurationError(
                f"Fuseau FORTIANALYZER_TIMEZONE inconnu : {connection_parameters.timezone_name}"
            ) from timezone_error

    @property
    def source_description(self) -> str:
        return f"FortiAnalyzer {self._connection_parameters.base_url} (ADOM {self._connection_parameters.adom})"

    def fetch_logs_between(self, period_start: datetime, period_end: datetime) -> list[RawFortiAnalyzerLog]:
        """Retourne tous les logs de la période, pour chaque type de log configuré. Lève une FortiAnalyzerError."""
        with self._open_http_client() as http_client:
            session_identifier = None if self._connection_parameters.uses_api_token else self._log_in(http_client)
            try:
                collected_logs: list[RawFortiAnalyzerLog] = []
                for log_type in self._connection_parameters.log_types:
                    collected_logs.extend(
                        self._search_logs(http_client, session_identifier, log_type, period_start, period_end)
                    )
                return collected_logs
            finally:
                if session_identifier is not None:
                    self._log_out(http_client, session_identifier)

    # --- Authentification ---

    def _log_in(self, http_client: httpx.Client) -> str:
        response = self._call(
            http_client,
            method="exec",
            params={
                "url": "/sys/login/user",
                "data": {
                    "user": self._connection_parameters.username,
                    "passwd": self._connection_parameters.password.get_secret_value(),
                },
            },
            session_identifier=None,
            operation_name="connexion",
        )
        if not response.session:
            raise FortiAnalyzerApiError("Connexion refusée : FortiAnalyzer n'a pas renvoyé de session.")
        return response.session

    def _log_out(self, http_client: httpx.Client, session_identifier: str) -> None:
        # Au mieux : une déconnexion ratée ne doit pas masquer le résultat (ou l'erreur) de la récupération.
        try:
            self._call(http_client, "exec", {"url": "/sys/logout"}, session_identifier, "déconnexion")
        except Exception:
            pass

    # --- Recherche de logs ---

    def _search_logs(
        self,
        http_client: httpx.Client,
        session_identifier: str | None,
        log_type: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[RawFortiAnalyzerLog]:
        search_url = f"/logview/adom/{self._connection_parameters.adom}/logsearch"
        search_parameters: dict[str, Any] = {
            "url": search_url,
            "apiver": LOG_SEARCH_API_VERSION,
            "logtype": log_type,
            "device": [{"devid": self._connection_parameters.device_identifier}],
            "time-order": "asc",
            "time-range": {
                "start": self._format_for_fortianalyzer(period_start),
                "end": self._format_for_fortianalyzer(period_end),
            },
        }
        if self._connection_parameters.search_filter:
            search_parameters["filter"] = self._connection_parameters.search_filter
        started_search = self._parse_result(
            self._call(http_client, "add", search_parameters, session_identifier, f"recherche des logs {log_type}"),
            LogSearchStartedResult,
            f"recherche des logs {log_type}",
        )
        search_task_url = f"{search_url}/{started_search.tid}"
        try:
            return self._read_all_search_pages(http_client, session_identifier, search_task_url, log_type)
        finally:
            try:
                self._call(
                    http_client,
                    "delete",
                    {"url": search_task_url, "apiver": LOG_SEARCH_API_VERSION},
                    session_identifier,
                    "libération de la recherche",
                )
            except Exception:
                pass  # libération au mieux : FortiAnalyzer purge aussi les recherches abandonnées

    def _read_all_search_pages(
        self, http_client: httpx.Client, session_identifier: str | None, search_task_url: str, log_type: str
    ) -> list[RawFortiAnalyzerLog]:
        operation_name = f"lecture des logs {log_type}"
        waited_seconds = 0.0
        # 1) Attendre la fin de la recherche (percentage = 100).
        while True:
            first_page = self._fetch_search_page(http_client, session_identifier, search_task_url, 0, operation_name)
            if first_page.percentage >= 100:
                break
            if waited_seconds >= LOG_SEARCH_MAXIMUM_WAIT_SECONDS:
                raise FortiAnalyzerConnectionError(
                    f"{operation_name} : recherche non terminée après {LOG_SEARCH_MAXIMUM_WAIT_SECONDS:.0f} s "
                    f"({first_page.percentage} %)."
                )
            self._wait(LOG_SEARCH_POLL_INTERVAL_SECONDS)
            waited_seconds += LOG_SEARCH_POLL_INTERVAL_SECONDS

        # 2) Lire les pages suivantes jusqu'au total annoncé (ou jusqu'à une page vide si le total est absent).
        collected_logs = list(first_page.data)
        total_count = first_page.total_count
        while first_page.data and (total_count is None or len(collected_logs) < total_count):
            if len(collected_logs) >= MAXIMUM_LOGS_PER_LOG_TYPE:
                raise FortiAnalyzerApiError(
                    f"{operation_name} : plus de {MAXIMUM_LOGS_PER_LOG_TYPE} logs sur la période ; "
                    "réduire la période (LOG_COLLECTION_INITIAL_LOOKBACK_HOURS) ou ajouter un filtre."
                )
            next_page = self._fetch_search_page(
                http_client, session_identifier, search_task_url, len(collected_logs), operation_name
            )
            if not next_page.data:
                break
            collected_logs.extend(next_page.data)
        return collected_logs

    def _fetch_search_page(
        self,
        http_client: httpx.Client,
        session_identifier: str | None,
        search_task_url: str,
        offset: int,
        operation_name: str,
    ) -> LogSearchPageResult:
        response = self._call(
            http_client,
            "get",
            {"url": search_task_url, "apiver": LOG_SEARCH_API_VERSION, "offset": offset, "limit": LOG_SEARCH_PAGE_SIZE},
            session_identifier,
            operation_name,
        )
        return self._parse_result(response, LogSearchPageResult, operation_name)

    # --- Transport JSON-RPC ---

    def _open_http_client(self) -> httpx.Client:
        headers = {"Content-Type": "application/json"}
        if self._connection_parameters.uses_api_token:
            headers["Authorization"] = f"Bearer {self._connection_parameters.api_token.get_secret_value()}"
        return httpx.Client(
            base_url=self._connection_parameters.base_url,
            headers=headers,
            verify=self._connection_parameters.tls_verification,
            timeout=self._connection_parameters.request_timeout_seconds,
            transport=self._http_transport,
        )

    def _call(
        self,
        http_client: httpx.Client,
        method: str,
        params: dict[str, Any],
        session_identifier: str | None,
        operation_name: str,
    ) -> JsonRpcResponse:
        """Envoie une requête JSON-RPC et vérifie l'enveloppe. Lève FortiAnalyzerConnectionError / ApiError."""
        request_body: dict[str, Any] = {
            "id": next(self._request_identifiers),
            "jsonrpc": "2.0",
            "method": method,
            "params": [params],
        }
        if session_identifier is not None:
            request_body["session"] = session_identifier
        try:
            http_response = http_client.post(JSON_RPC_PATH, json=request_body)
        except httpx.TimeoutException as timeout_error:
            raise FortiAnalyzerConnectionError(f"{operation_name} : délai dépassé.") from timeout_error
        except httpx.HTTPError as http_error:
            # Le nom de la classe suffit (ConnectError, SSL...) : le message d'origine peut contenir l'URL complète.
            raise FortiAnalyzerConnectionError(
                f"{operation_name} : FortiAnalyzer injoignable ({type(http_error).__name__}). "
                "Vérifier l'adresse, le réseau et le certificat TLS."
            ) from http_error
        if http_response.status_code != 200:
            raise FortiAnalyzerConnectionError(f"{operation_name} : réponse HTTP {http_response.status_code}.")
        try:
            response = JsonRpcResponse.model_validate(http_response.json())
        except (ValueError, ValidationError) as format_error:
            raise FortiAnalyzerConnectionError(f"{operation_name} : réponse illisible (format inattendu).") from format_error

        if response.error is not None:
            raise FortiAnalyzerApiError(
                f"{operation_name} : erreur FortiAnalyzer {response.error.code} « {response.error.message} »."
            )
        if isinstance(response.result, list):
            for result_item in response.result:
                if result_item.status is not None and result_item.status.code != 0:
                    raise FortiAnalyzerApiError(
                        f"{operation_name} : erreur FortiAnalyzer {result_item.status.code} "
                        f"« {result_item.status.message} »."
                    )
        elif isinstance(response.result, dict):
            status = response.result.get("status")
            if isinstance(status, dict) and status.get("code") not in (None, 0):
                raise FortiAnalyzerApiError(
                    f"{operation_name} : erreur FortiAnalyzer {status.get('code')} « {status.get('message', '')} »."
                )
        return response

    @staticmethod
    def _parse_result(response: JsonRpcResponse, result_model, operation_name: str):
        """Extrait et valide le résultat utile (objet direct, ou `data` du premier élément de liste)."""
        result_payload: Any = response.result
        if isinstance(result_payload, list):
            result_payload = result_payload[0].data if result_payload else None
        try:
            return result_model.model_validate(result_payload)
        except ValidationError as format_error:
            raise FortiAnalyzerConnectionError(
                f"{operation_name} : résultat inattendu (champs manquants ou invalides)."
            ) from format_error

    def _format_for_fortianalyzer(self, moment: datetime) -> str:
        return moment.astimezone(self._fortianalyzer_timezone).strftime(FORTIANALYZER_DATETIME_FORMAT)
