"""Accès aux informations historisées de la mémoire projet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.project_memory.models import (
    EvidenceState,
    MemoryItemType,
    ProjectDimensionState,
    ProjectMemoryItem,
    ProvenanceType,
)


@dataclass(frozen=True)
class MemoryCounts:
    total: int
    by_state: dict[str, int]
    by_dimension: dict[str, int]


class ProjectMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: UUID) -> ProjectMemoryItem | None:
        return await self.session.get(ProjectMemoryItem, item_id)

    async def get_by_deduplication_key(
        self,
        project_id: UUID,
        key: str,
    ) -> ProjectMemoryItem | None:
        result = await self.session.execute(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.deduplication_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        project_id: UUID,
        dimension: str,
        item_type: MemoryItemType,
        evidence_state: EvidenceState,
        statement: str,
        provenance_type: ProvenanceType,
        created_by_id: UUID | None,
        deduplication_key: str | None = None,
        supersedes_id: UUID | None = None,
        occurred_at: datetime | None = None,
        expires_at: datetime | None = None,
        attributes: dict | None = None,
    ) -> ProjectMemoryItem:
        item = ProjectMemoryItem(
            project_id=project_id,
            dimension=dimension,
            item_type=item_type,
            evidence_state=evidence_state,
            statement=statement,
            provenance_type=provenance_type,
            created_by_id=created_by_id,
            deduplication_key=deduplication_key,
            supersedes_id=supersedes_id,
            occurred_at=occurred_at,
            expires_at=expires_at,
            attributes=attributes or {},
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        dimension: str | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[ProjectMemoryItem]:
        stmt = select(ProjectMemoryItem).where(ProjectMemoryItem.project_id == project_id)
        if dimension is not None:
            stmt = stmt.where(ProjectMemoryItem.dimension == dimension)
        if active_only:
            stmt = stmt.where(ProjectMemoryItem.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(ProjectMemoryItem.created_at.desc()).limit(limit))
        return list(result.scalars())

    async def deactivate(self, item: ProjectMemoryItem) -> None:
        item.is_active = False
        await self.session.flush()

    async def list_dimension_states(self, project_id: UUID) -> list[ProjectDimensionState]:
        result = await self.session.execute(
            select(ProjectDimensionState)
            .where(ProjectDimensionState.project_id == project_id)
            .order_by(ProjectDimensionState.dimension)
        )
        return list(result.scalars())

    async def upsert_dimension_state(
        self,
        *,
        project_id: UUID,
        dimension: str,
        score: int | None,
        confidence: float,
        evidence_state: EvidenceState,
        rationale: str,
        contradictions: list,
        missing_information: str,
        next_action: dict,
        last_score_run_id: UUID | None,
        evaluated_at: datetime | None,
    ) -> ProjectDimensionState:
        result = await self.session.execute(
            select(ProjectDimensionState).where(
                ProjectDimensionState.project_id == project_id,
                ProjectDimensionState.dimension == dimension,
            )
        )
        state = result.scalar_one_or_none()
        values = {
            "score": score,
            "confidence": confidence,
            "evidence_state": evidence_state,
            "rationale": rationale,
            "contradictions": contradictions,
            "missing_information": missing_information,
            "next_action": next_action,
            "last_score_run_id": last_score_run_id,
            "evaluated_at": evaluated_at,
        }
        if state is None:
            state = ProjectDimensionState(project_id=project_id, dimension=dimension, **values)
            self.session.add(state)
        else:
            for field, value in values.items():
                setattr(state, field, value)
        await self.session.flush()
        return state

    async def counts_for_project(self, project_id: UUID) -> MemoryCounts:
        base_filter = (
            ProjectMemoryItem.project_id == project_id,
            ProjectMemoryItem.is_active.is_(True),
        )
        total = await self.session.scalar(select(func.count(ProjectMemoryItem.id)).where(*base_filter))
        by_state_rows = await self.session.execute(
            select(ProjectMemoryItem.evidence_state, func.count(ProjectMemoryItem.id))
            .where(*base_filter)
            .group_by(ProjectMemoryItem.evidence_state)
        )
        by_dimension_rows = await self.session.execute(
            select(ProjectMemoryItem.dimension, func.count(ProjectMemoryItem.id))
            .where(*base_filter)
            .group_by(ProjectMemoryItem.dimension)
        )
        return MemoryCounts(
            total=int(total or 0),
            by_state={state.value: count for state, count in by_state_rows},
            by_dimension={dimension: count for dimension, count in by_dimension_rows},
        )
