"""Accès données scoring — grilles + runs de score."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.scoring.models import ScoreRun, ScoreSource, ScoringGrid


class ScoringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self) -> ScoringGrid | None:
        result = await self.session.execute(select(ScoringGrid).where(ScoringGrid.is_active.is_(True)).limit(1))
        return result.scalar_one_or_none()

    async def get_by_version(self, version: str) -> ScoringGrid | None:
        result = await self.session.execute(select(ScoringGrid).where(ScoringGrid.version == version))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        version: str,
        pillars: list[dict],
        axes: list[dict],
        category_weights: dict[str, dict[str, float]],
        is_active: bool,
        scale_max: int = 10,
    ) -> ScoringGrid:
        grid = ScoringGrid(
            version=version,
            pillars=pillars,
            axes=axes,
            category_weights=category_weights,
            is_active=is_active,
            scale_max=scale_max,
        )
        self.session.add(grid)
        await self.session.flush()
        return grid


class ScoreRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: UUID,
        diagnostic_id: UUID | None,
        report_id: UUID | None,
        grid_version: str,
        prompt_version: str,
        model: str,
        source: ScoreSource,
        raw_output: dict | None,
        axes: dict[str, int],
        justifications: dict[str, str] | None,
        pillars: dict[str, int],
        overall: int,
        n_passes: int = 1,
        confidence: float | None = None,
        spread: dict[str, int] | None = None,
        needs_review: bool = False,
    ) -> ScoreRun:
        run = ScoreRun(
            project_id=project_id,
            diagnostic_id=diagnostic_id,
            report_id=report_id,
            grid_version=grid_version,
            prompt_version=prompt_version,
            model=model,
            source=source,
            raw_output=raw_output,
            axes=axes,
            justifications=justifications,
            pillars=pillars,
            overall=overall,
            n_passes=n_passes,
            confidence=confidence,
            spread=spread,
            needs_review=needs_review,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id(self, run_id: UUID) -> ScoreRun | None:
        return await self.session.get(ScoreRun, run_id)

    async def list_for_project(self, project_id: UUID) -> list[ScoreRun]:
        result = await self.session.execute(
            select(ScoreRun).where(ScoreRun.project_id == project_id).order_by(ScoreRun.created_at.desc())
        )
        return list(result.scalars())
