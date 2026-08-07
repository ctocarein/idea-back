"""Mémoire projet : informations sourcées et état explicable par dimension."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _enum_values(enum: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum]


class EvidenceState(str, Enum):
    UNKNOWN = "unknown"
    INFERRED = "inferred"
    DECLARED = "declared"
    SUPPORTED = "supported"
    VERIFIED = "verified"
    STALE = "stale"


class MemoryItemType(str, Enum):
    FACT = "fact"
    DECLARATION = "declaration"
    HYPOTHESIS = "hypothesis"
    CONTRADICTION = "contradiction"
    EVIDENCE = "evidence"
    DECISION = "decision"


class ProvenanceType(str, Enum):
    NARRATIVE = "narrative"
    USER_ANSWER = "user_answer"
    DOCUMENT = "document"
    ACADEMY = "academy"
    PITCH = "pitch"
    MENTOR = "mentor"
    PROGRAM = "program"
    METRIC = "metric"
    SYSTEM = "system"


class ProjectMemoryItem(Base):
    """Une information atomique, sourcée et historisée concernant un projet."""

    __tablename__ = "project_memory_items"
    __table_args__ = (
        CheckConstraint("dimension ~ '^d([1-9]|1[0-2])$'", name="ck_project_memory_dimension"),
        UniqueConstraint("project_id", "deduplication_key", name="uq_project_memory_deduplication"),
        Index("ix_project_memory_project_dimension", "project_id", "dimension"),
        Index("ix_project_memory_project_state", "project_id", "evidence_state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(3))
    item_type: Mapped[MemoryItemType] = mapped_column(
        SAEnum(MemoryItemType, native_enum=False, values_callable=_enum_values),
    )
    evidence_state: Mapped[EvidenceState] = mapped_column(
        SAEnum(EvidenceState, native_enum=False, values_callable=_enum_values),
    )
    statement: Mapped[str] = mapped_column(Text)

    provenance_type: Mapped[ProvenanceType] = mapped_column(
        SAEnum(ProvenanceType, native_enum=False, values_callable=_enum_values),
    )
    source_ref: Mapped[str | None] = mapped_column(String(200), default=None)
    source_excerpt: Mapped[str | None] = mapped_column(Text, default=None)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    deduplication_key: Mapped[str | None] = mapped_column(String(200), default=None)

    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    verified_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    verified_at: Mapped[datetime | None] = mapped_column(default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_memory_items.id", ondelete="SET NULL"), default=None
    )
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ProjectDimensionState(Base):
    """Dernier état lisible d'une dimension, distinct des preuves historiques."""

    __tablename__ = "project_dimension_states"
    __table_args__ = (
        CheckConstraint("dimension ~ '^d([1-9]|1[0-2])$'", name="ck_project_dimension_state_dimension"),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 10", name="ck_project_dimension_state_score"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_project_dimension_state_confidence",
        ),
        UniqueConstraint("project_id", "dimension", name="uq_project_dimension_state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(3))
    score: Mapped[int | None] = mapped_column(default=None)
    confidence: Mapped[float] = mapped_column(default=0.0)
    evidence_state: Mapped[EvidenceState] = mapped_column(
        SAEnum(EvidenceState, native_enum=False, values_callable=_enum_values),
        default=EvidenceState.UNKNOWN,
    )
    rationale: Mapped[str] = mapped_column(Text, default="")
    contradictions: Mapped[list] = mapped_column(JSONB, default=list)
    missing_information: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_score_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("score_runs.id", ondelete="SET NULL"), default=None, index=True
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
