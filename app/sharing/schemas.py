"""DTO partage."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ShareCreateIn(BaseModel):
    consent: bool = Field(description="Consentement explicite du porteur au partage (RGPD).")


class ShareOut(BaseModel):
    token: str
    path: str  # à composer avec le domaine front : <front>/shared/{token}


class SharedFicheOut(BaseModel):
    # Lecture jury/incubateur (triple-lecture) : le credential + une synthèse, pas les internes.
    project_title: str
    sector: str
    maturity: str | None
    overall_100: int
    summary: str
    strengths: list[str]
    scored_by: str = "Ideaxion"
