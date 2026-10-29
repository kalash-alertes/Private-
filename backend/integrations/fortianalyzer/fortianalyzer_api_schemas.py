"""Validation (Pydantic) des réponses de l'API JSON-RPC de FortiAnalyzer.

FortiAnalyzer répond sous deux formes selon l'appel :
- forme « classique » (connexion, déconnexion) : `{"result": [{"status": {"code": 0, "message": "OK"}, "data": ...}],
  "session": "..."}` ;
- forme « logview apiver 3 » (recherche de logs) : `{"result": {"tid": 42}}` ou
  `{"result": {"data": [...], "percentage": 100, "total-count": 250, ...}}`.
Une erreur peut arriver dans `error` (`{"code": ..., "message": ...}`) ou dans `result[].status.code` ≠ 0.

Les formats exacts dépendent de la version de FortiAnalyzer : ces schémas acceptent les champs supplémentaires
(`extra="allow"`) et ne rendent obligatoire que ce qui est indispensable.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JsonRpcStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int
    message: str = ""


class JsonRpcError(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int | str | None = None
    message: str = ""


class JsonRpcResultItem(BaseModel):
    """Élément de `result` dans la forme classique."""

    model_config = ConfigDict(extra="allow")

    status: JsonRpcStatus | None = None
    url: str | None = None
    data: Any = None


class JsonRpcResponse(BaseModel):
    """Enveloppe de toute réponse. `result` est une liste (forme classique) ou un objet (logview apiver 3)."""

    model_config = ConfigDict(extra="allow")

    result: list[JsonRpcResultItem] | dict[str, Any] | None = None
    error: JsonRpcError | None = None
    session: str | None = None


class LogSearchStartedResult(BaseModel):
    """Réponse au lancement d'une recherche : identifiant de la tâche de recherche (`tid`)."""

    model_config = ConfigDict(extra="allow")

    tid: int


class LogSearchPageResult(BaseModel):
    """Une page de résultats. `percentage` < 100 : FortiAnalyzer cherche encore."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    data: list[dict[str, Any]] = Field(default_factory=list)
    percentage: int = 100
    total_count: int | None = Field(default=None, alias="total-count")
    return_lines: int | None = Field(default=None, alias="return-lines")
    status: JsonRpcStatus | None = None
