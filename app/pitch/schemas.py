"""Schémas de l'éditeur de pitch (V1.2)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PitchSectionOut(BaseModel):
    key: str
    title: str
    content: str
    hint: str = ""


class PitchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    sections: list[PitchSectionOut]
    template_id: str = "base"
    slides: list[dict] = []
    updated_at: datetime


class DeckGenerateIn(BaseModel):
    # Source optionnelle : texte collé / pitch importé. Vide → on part des sections.
    source: str | None = None


class TemplateIn(BaseModel):
    template_id: str


class SlideUpdateIn(BaseModel):
    """Champs d'une slide édités par le porteur (édition structurée)."""

    layout: str | None = None
    title: str | None = None
    subtitle: str | None = None
    bullets: list[str] | None = None
    stat: dict | None = None
    chart: dict | None = None
    image_keyword: str | None = None
    caption: str | None = None


class SlidesReorderIn(BaseModel):
    order: list[int]  # nouvel ordre = indices actuels réagencés


class SectionUpdateIn(BaseModel):
    content: str = Field(default="", max_length=8000)


class SectionGenerateOut(BaseModel):
    """Contenu proposé par l'IA pour une section (le porteur décide de l'adopter)."""

    key: str
    content: str
