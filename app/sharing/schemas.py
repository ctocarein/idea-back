"""DTO partage."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

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


class ShareStatsOut(BaseModel):
    id: UUID
    project_id: UUID
    project_title: str
    # Renseigné uniquement quand un ancien stockage permettait encore de relire
    # le token. Les nouveaux liens sont révélés une seule fois à leur création.
    share_url: str
    is_active: bool
    expires_at: datetime
    view_count: int
    last_viewed_at: datetime | None
    created_at: datetime


class ProjectVisibilityOut(BaseModel):
    project_id: UUID
    project_title: str
    is_public: bool
