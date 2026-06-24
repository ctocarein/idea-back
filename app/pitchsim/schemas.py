"""DTO pitchsim — rubrique, comités, decks."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SlideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    position: int
    title: str
    extracted_text: str


class DeckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    project_id: UUID | None
    slides: list[SlideOut] = []


# --- Rubrique & comités (lecture) ---


class PersonaOut(BaseModel):
    name: str
    role: str
    personality: str
    style: str
    obsession: str


class CommitteeOut(BaseModel):
    key: str
    label: str
    personas: list[PersonaOut]
