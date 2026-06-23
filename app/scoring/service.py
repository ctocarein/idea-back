"""Service scoring — expose la grille active et produit des scores ROBUSTES.

`build_score`/`build_consensus_score` valident strictement contre la grille (version-correcte,
échelle /10 en v2), agrègent de façon déterministe (piliers + global pondéré) et enregistrent
un `ScoreRun` rejouable. Ne commitent PAS : l'appelant (worker, ajustement analyste) commite.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.core.errors import NotFoundError
from app.scoring import engine
from app.scoring.ensemble import EnsembleThresholds, consensus
from app.scoring.models import ScoreSource, ScoringGrid
from app.scoring.repository import ScoreRunRepository, ScoringRepository
from app.scoring.schemas import AxisOut, GridOut, PillarOut, ScoreResult


class ScoringService:
    def __init__(
        self,
        repo: ScoringRepository,
        runs: ScoreRunRepository | None = None,
    ) -> None:
        self.repo = repo
        self.runs = runs

    async def get_active_grid(self) -> GridOut:
        grid = await self.repo.get_active()
        if grid is None:
            raise NotFoundError("Aucune grille Radar active. Lancer le seed (make seed).")
        return self._to_grid_out(grid)

    @staticmethod
    def _to_grid_out(grid: ScoringGrid) -> GridOut:
        return GridOut(
            version=grid.version,
            scale_max=grid.scale_max,
            pillars=[PillarOut(**p) for p in grid.pillars],
            axes=[AxisOut(**axis) for axis in grid.axes],
            category_weights=grid.category_weights,
        )

    async def _resolve_grid(self, grid_version: str | None) -> ScoringGrid:
        grid = await self.repo.get_by_version(grid_version) if grid_version else await self.repo.get_active()
        if grid is None:
            raise NotFoundError("Grille Radar introuvable pour ce score.")
        return grid

    async def build_score(
        self,
        *,
        project_id: UUID,
        diagnostic_id: UUID | None,
        report_id: UUID | None,
        category: str,
        axes: dict[str, int],
        justifications: dict[str, str] | None = None,
        grid_version: str | None = None,
        prompt_version: str = "",
        model: str = "",
        source: ScoreSource = ScoreSource.LLM,
        raw_output: dict | None = None,
    ) -> ScoreResult:
        if self.runs is None:
            raise RuntimeError("build_score nécessite un ScoreRunRepository.")
        grid = await self._resolve_grid(grid_version)

        engine.validate_axes(grid.axes, axes, grid.scale_max)
        pillars = engine.pillar_scores(grid.axes, axes)
        overall = engine.weighted_overall(grid.axes, grid.category_weights, category, axes)

        run = await self.runs.create(
            project_id=project_id,
            diagnostic_id=diagnostic_id,
            report_id=report_id,
            grid_version=grid.version,
            prompt_version=prompt_version,
            model=model,
            source=source,
            raw_output=raw_output,
            axes=axes,
            justifications=justifications,
            pillars=pillars,
            overall=overall,
        )
        return ScoreResult(
            run_id=run.id,
            grid_version=grid.version,
            scale_max=grid.scale_max,
            axes=axes,
            pillars=pillars,
            overall=overall,
        )

    async def build_consensus_score(
        self,
        *,
        project_id: UUID,
        diagnostic_id: UUID | None,
        report_id: UUID | None,
        category: str,
        passes: Sequence[dict[str, int]],
        justifications: dict[str, str] | None = None,
        grid_version: str | None = None,
        prompt_version: str = "",
        model: str = "",
        raw_outputs: list[dict] | None = None,
        thresholds: EnsembleThresholds | None = None,
    ) -> ScoreResult:
        # Variante ROBUSTE : N passes → consensus (médiane) + confiance (étendue).
        if self.runs is None:
            raise RuntimeError("build_consensus_score nécessite un ScoreRunRepository.")
        grid = await self._resolve_grid(grid_version)

        keys = engine.axis_keys(grid.axes)
        cons = consensus(passes, keys, thresholds)

        engine.validate_axes(grid.axes, cons.axes, grid.scale_max)
        pillars = engine.pillar_scores(grid.axes, cons.axes)
        overall = engine.weighted_overall(grid.axes, grid.category_weights, category, cons.axes)

        run = await self.runs.create(
            project_id=project_id,
            diagnostic_id=diagnostic_id,
            report_id=report_id,
            grid_version=grid.version,
            prompt_version=prompt_version,
            model=model,
            source=ScoreSource.LLM,
            raw_output={"passes": list(passes), "raw_outputs": raw_outputs},
            axes=cons.axes,
            justifications=justifications,
            pillars=pillars,
            overall=overall,
            n_passes=cons.n_passes,
            confidence=cons.confidence,
            spread=cons.per_axis_spread,
            needs_review=cons.needs_human_review,
        )
        return ScoreResult(
            run_id=run.id,
            grid_version=grid.version,
            scale_max=grid.scale_max,
            axes=cons.axes,
            pillars=pillars,
            overall=overall,
            confidence=cons.confidence,
            needs_review=cons.needs_human_review,
            uncertain_axes=cons.uncertain_axes,
            spread=cons.per_axis_spread,
        )
