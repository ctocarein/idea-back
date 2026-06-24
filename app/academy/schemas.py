"""DTO Academy — leçons, progression, sessions « construire guidé »."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    topic: str
    summary: str
    position: int


class LessonDetailOut(LessonOut):
    body: str


class AcademyProgressOut(BaseModel):
    total_lessons: int
    completed_count: int
    completed_lesson_ids: list[UUID]


# --- Construire guidé ---


class GuidedStartIn(BaseModel):
    section: str = Field(min_length=1, max_length=80)  # ex. "modele_economique"
    project_id: UUID | None = None


class GuidedTurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class GuidedDraftIn(BaseModel):
    draft: str = Field(max_length=20000)


class GuidedSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    section: str
    draft: str
    turns: list[dict]
