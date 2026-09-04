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
    # Levier typé ({type, topic}) — DATA de la grille, pas une URL : le client résout
    # l'intent selon ce qui existe chez lui. Exposé pour que le front cesse d'en tenir un
    # miroir en dur, qui dériverait en silence de la grille qui a produit le score.
    lever: dict[str, str] | None = None


class MaturityLevel(BaseModel):
    key: str
    label: str
    min: int
    max: int
    description: str
    tone: str  # fragile | watch | good | strong


class GridOut(BaseModel):
    # Réponse de GET /scoring/grid : la grille active (v2 : 12 dims / 4 piliers / 10).
    version: str
    scale_max: int = 10  # échelle d'une DIMENSION
    # Échelle du score global et des paliers de maturité. Explicite pour que le front
    # n'ait rien à supposer : c'est un pourcentage normalisé, pas une note /100.
    overall_scale: int = 100
    pillars: list[PillarOut]
    axes: list[AxisOut]
    category_weights: dict[str, dict[str, float]] = Field(default_factory=dict)
    # Secteurs pour lesquels une pondération est calibrée DANS CETTE grille. Les autres
    # sont notés à poids neutre — assumé, et dit au porteur (cf. `sector_calibrated`).
    calibrated_sectors: list[str] = Field(default_factory=list)
    # SOURCE UNIQUE des paliers (SPEC C4). Le front ne redéfinit aucune borne.
    maturity_levels: list[MaturityLevel] = Field(default_factory=list)


class RadarScore(BaseModel):
    # Score Radar = valeurs par dimension + version de grille.
    model_config = ConfigDict(populate_by_name=True)

    grid_version: str = Field(
        serialization_alias="gridVersion",
        validation_alias=AliasChoices("grid_version", "gridVersion"),
    )
    axes: dict[str, int]

    # Le global est SERVI, jamais recalculé par le client (SPEC_SCORING_INTEGRITY C3).
    # Tant que le back ne le servait pas, le front était contraint de le réagréger —
    # sans les poids, sur une autre échelle. Le contrat était incomplet, pas le front.
    # Optionnels : compatibilité ascendante avec les bilans déjà persistés.
    overall: int | None = None  # 0..100, pondéré, source de vérité
    pillars: dict[str, int] | None = None  # 0..scale_max par pilier, moyenne simple
    sector_calibrated: bool | None = Field(  # cf. C2 — pondération sectorielle disponible ?
        default=None,
        serialization_alias="sectorCalibrated",
        validation_alias=AliasChoices("sector_calibrated", "sectorCalibrated"),
    )


class ScoreResult(BaseModel):
    # Résultat agrégé déterministe d'un scoring (retourné par le service).
    run_id: UUID
    grid_version: str
    scale_max: int = 10
    axes: dict[str, int]
    pillars: dict[str, int]  # 4 piliers (vue porteur), moyenne simple sur `scale_max`
    overall: int  # score global pondéré NORMALISÉ 0..100 (chiffre de décision)
    # Faux = aucune pondération calibrée pour ce secteur, toutes les dimensions comptent
    # également. À afficher dans le bilan plutôt qu'à taire.
    sector_calibrated: bool = False
    # Incertitude (renseignée pour un score d'ensemble ; sinon valeurs neutres).
    confidence: float | None = None
    needs_review: bool = False
    uncertain_axes: list[str] = Field(default_factory=list)
    spread: dict[str, int] | None = None


def radar_payload(result: ScoreResult) -> dict:
    """Payload `report.radar_score` — point d'écriture UNIQUE du score persisté.

    Le global voyage avec le radar : sans lui, tout client est contraint de réagréger
    lui-même, sans les poids et sur son échelle (SPEC_SCORING_INTEGRITY C3). Le score
    est figé ici et n'est JAMAIS recalculé à l'affichage.

    Clés en camelCase, comme `gridVersion` déjà persisté : le DTO accepte les deux formes.
    """
    return {
        "gridVersion": result.grid_version,
        "axes": result.axes,
        "overall": result.overall,
        "pillars": result.pillars,
        "sectorCalibrated": result.sector_calibrated,
    }
