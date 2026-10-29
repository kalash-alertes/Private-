"""Faux serveur FortiAnalyzer pour les tests : répond aux appels JSON-RPC via httpx.MockTransport (aucun réseau).

Il imite le déroulé documenté : connexion → recherche (tid) → avancement (percentage) → pages → libération →
déconnexion, et enregistre chaque requête reçue pour que les tests vérifient ce que le client a envoyé.
"""

import json
from typing import Any

import httpx

FAKE_SESSION_IDENTIFIER = "session-synthetique-123"
FAKE_SEARCH_TASK_IDENTIFIER = 42


class FakeFortiAnalyzerServer:
    def __init__(
        self,
        logs_by_log_type: dict[str, list[dict[str, Any]]] | None = None,
        searches_in_progress_before_completion: int = 0,
        login_error_code: int | None = None,
        http_status_code: int = 200,
    ) -> None:
        self.logs_by_log_type = logs_by_log_type or {}
        self.remaining_in_progress_answers = searches_in_progress_before_completion
        self.login_error_code = login_error_code
        self.http_status_code = http_status_code
        self.received_requests: list[dict[str, Any]] = []
        self.received_headers: list[httpx.Headers] = []
        self._current_log_type: str | None = None

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle_request)

    def calls_to(self, url_fragment: str, method: str | None = None) -> list[dict[str, Any]]:
        return [
            request
            for request in self.received_requests
            if url_fragment in request["params"][0]["url"] and (method is None or request["method"] == method)
        ]

    def _handle_request(self, http_request: httpx.Request) -> httpx.Response:
        if self.http_status_code != 200:
            return httpx.Response(self.http_status_code, text="erreur serveur synthétique")
        request_body = json.loads(http_request.content)
        self.received_requests.append(request_body)
        self.received_headers.append(http_request.headers)
        params = request_body["params"][0]
        url, method = params["url"], request_body["method"]

        if url == "/sys/login/user":
            if self.login_error_code is not None:
                return self._classic_answer(url, self.login_error_code, "Login fail")
            return httpx.Response(200, json={**self._classic_body(url, 0, "OK"), "session": FAKE_SESSION_IDENTIFIER})
        if url == "/sys/logout":
            return httpx.Response(200, json=self._classic_body(url, 0, "OK"))
        if url.endswith("/logsearch") and method == "add":
            self._current_log_type = params["logtype"]
            return httpx.Response(200, json={"id": request_body["id"], "result": {"tid": FAKE_SEARCH_TASK_IDENTIFIER}})
        if url.endswith(f"/logsearch/{FAKE_SEARCH_TASK_IDENTIFIER}") and method == "get":
            if self.remaining_in_progress_answers > 0:
                self.remaining_in_progress_answers -= 1
                return httpx.Response(200, json={"id": request_body["id"], "result": {"data": [], "percentage": 40}})
            all_logs = self.logs_by_log_type.get(self._current_log_type, [])
            page = all_logs[params["offset"] : params["offset"] + params["limit"]]
            return httpx.Response(
                200,
                json={
                    "id": request_body["id"],
                    "result": {"data": page, "percentage": 100, "total-count": len(all_logs), "return-lines": len(page)},
                },
            )
        if method == "delete":
            return httpx.Response(200, json={"id": request_body["id"], "result": {"status": {"code": 0}}})
        return self._classic_answer(url, -6, "Invalid url")

    @staticmethod
    def _classic_body(url: str, code: int, message: str) -> dict[str, Any]:
        return {"id": 1, "result": [{"status": {"code": code, "message": message}, "url": url}]}

    def _classic_answer(self, url: str, code: int, message: str) -> httpx.Response:
        return httpx.Response(200, json=self._classic_body(url, code, message))
