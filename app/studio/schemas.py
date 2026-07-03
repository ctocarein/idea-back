"""Schémas d'E/S du Studio (logo)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VariationOut(BaseModel):
    # Un concept proposé : son spec (pour sélection) + son rendu SVG (pour l'aperçu).
    spec: dict
    svg: str


class LogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    spec: dict | None
    svg: str | None  # rendu du spec courant (None tant que rien n'est généré)
    variations: list[VariationOut]
    updated_at: datetime


class LogoUpdateIn(BaseModel):
    # Édition partielle du logo courant. Tous les champs sont optionnels.
    name: str | None = None
    tagline: str | None = None
    mark_type: str | None = None
    icon: str | None = None
    geometric: str | None = None
    monogram: str | None = None
    layout: str | None = None
    container: str | None = None
    font: str | None = None
    palette: dict | None = None
    # Peaufinage : wordmark multicolore + réglages du slogan.
    # NB : pour EFFACER name_parts (repasser en couleur unie), envoyer [] (liste vide),
    # pas null (les null sont ignorés par exclude_none côté service).
    name_color: str | None = None
    name_parts: list[dict] | None = None
    tagline_font: str | None = None
    tagline_size: str | None = None
    tagline_color: str | None = None


class LogoSelectIn(BaseModel):
    index: int
