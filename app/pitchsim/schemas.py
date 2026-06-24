"""DTO pitchsim — rubrique, comités, decks."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


# --- Session & tours ---


class SessionStartIn(BaseModel):
    committee_key: str = Field(min_length=1, max_length=40)
    mode: str = Field(default="slides", pattern="^(slides|camera)$")
    deck_id: UUID | None = None
    project_id: UUID | None = None
    # Options (Écran 1) :
    imprevus: bool = True
    hard_questions: bool = True
    silence: bool = False
    duration_min: int = Field(default=5, ge=1, le=20)


class SlideSubmitIn(BaseModel):
    narration: str = Field(min_length=1, max_length=8000)
    slide_id: UUID | None = None


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    shown_slide_id: UUID | None = None


class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    actor: str
    kind: str
    content: str
    meta: dict


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    committee_key: str
    mode: str
    status: str
    config: dict
    turns: list[TurnOut] = []
