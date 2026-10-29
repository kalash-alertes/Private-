"""Pagination commune à toutes les listes de l'API (par décalage : `limit` + `offset`).

Choix : la pagination par décalage suffit pour les volumes V1 (logs critiques uniquement). Si les volumes deviennent
importants, passer à une pagination par curseur (le tri est déjà déterministe : date puis identifiant).
"""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE_SIZE = 50
MAXIMUM_PAGE_SIZE = 200

PageItem = TypeVar("PageItem")


class PaginationParameters(BaseModel):
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAXIMUM_PAGE_SIZE)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel, Generic[PageItem]):
    """Une page de résultats. `total` = nombre total d'éléments correspondant aux filtres (toutes pages confondues)."""

    items: list[PageItem]
    total: int
    limit: int
    offset: int


def read_pagination_parameters(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAXIMUM_PAGE_SIZE, description="Taille de la page"),
    offset: int = Query(default=0, ge=0, description="Nombre d'éléments à sauter"),
) -> PaginationParameters:
    """Dépendance FastAPI : lit et valide `limit` et `offset` dans la query string."""
    return PaginationParameters(limit=limit, offset=offset)
