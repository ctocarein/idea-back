"""Pagination offset standard, réutilisable par tous les repositories.

Cursor possible plus tard ; l'offset suffit au MVP (listes admin, marketplace mentor).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    # Paramètres de requête communs (?page=1&size=20).
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class Page(BaseModel, Generic[T]):
    # Enveloppe de réponse paginée uniforme.
    items: list[T]
    total: int
    page: int
    size: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PageParams) -> Page[T]:
        return cls(items=items, total=total, page=params.page, size=params.size)
