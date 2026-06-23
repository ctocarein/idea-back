"""DTO scoring — grille v2 ancrée exposée, score Radar, résultat agrégé."""

from __future__ import annotations

from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AnchorOut(BaseModel):
    min: int
    max: int
    label: str


class PillarOut(BaseModel):
    key: str
    label: str
    question: str


class AxisOut(BaseModel):
    key: str
    code: str = ""
    label: str
    pillar: str
    central_question: str = ""
    anchors: list[AnchorOut] = Field(default_factory=list)
    guiding_questions: list[str] = Field(default_factory=list)


class GridOut(BaseModel):
    # Réponse de GET /scoring/grid : la grille active (v2 : 12 dims / 4 piliers / 10).
    version: str
    scale_max: int = 10
    pillars: list[PillarOut]
    axes: list[AxisOut]
    category_weights: dict[str, dict[str, float]] = Field(default_factory=dict)


class RadarScore(BaseModel):
    # Score Radar = valeurs par dimension + version de grille.
    model_config = ConfigDict(populate_by_name=True)

    grid_version: str = Field(
        serialization_alias="gridVersion",
        validation_alias=AliasChoices("grid_version", "gridVersion"),
    )
    axes: dict[str, int]


class ScoreResult(BaseModel):
    # Résultat agrégé déterministe d'un scoring (retourné par le service).
    run_id: UUID
    grid_version: str
    scale_max: int = 10
    axes: dict[str, int]
    pillars: dict[str, int]  # 4 piliers (vue porteur)
    overall: int  # score global pondéré (chiffre de décision)
    # Incertitude (renseignée pour un score d'ensemble ; sinon valeurs neutres).
    confidence: float | None = None
    needs_review: bool = False
    uncertain_axes: list[str] = Field(default_factory=list)
    spread: dict[str, int] | None = None
