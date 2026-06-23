"""DTO reports — bilan in-app + rapport de pré-diagnostic structuré.

`DiagnosticReport` = la couche STRUCTURÉE du rapport (au-delà des 12 scores) : description,
verdict, matrice de risques, concurrents, avancement, recommandations priorisées, next steps.
Tolérante (extra ignoré, champs optionnels) : une section manquante ne casse jamais le bilan.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reports.models import ReportStatus
from app.scoring.schemas import RadarScore

_Tolerant = ConfigDict(extra="ignore")


class ReportDescription(BaseModel):
    model_config = _Tolerant
    problem: str = ""
    solution: str = ""
    target_client: str = ""
    business_model: str = ""


class StrengthItem(BaseModel):
    model_config = _Tolerant
    text: str = ""
    dimension: str | None = None  # ex. "d3"


class RiskItem(BaseModel):
    model_config = _Tolerant
    text: str = ""
    probability: str = "medium"  # high | medium | low
    severity: str = "medium"  # critical | high | medium | low


class Competitor(BaseModel):
    model_config = _Tolerant
    name: str = ""
    type: str = "indirect"  # direct | indirect
    description: str = ""
    threat: str = "medium"  # high | medium | low


class ProgressMetrics(BaseModel):
    model_config = _Tolerant
    stage: str | None = None
    team_size: int | None = None
    customers: int | None = None
    revenue: int | None = None  # FCFA
    funding: int | None = None  # FCFA


class Verdict(BaseModel):
    model_config = _Tolerant
    status: str = "conditional"  # go | conditional | nogo
    label: str = ""
    analysis: str = ""


class Recommendation(BaseModel):
    model_config = _Tolerant
    priority: int = 3
    title: str = ""
    description: str = ""


class NextStep(BaseModel):
    model_config = _Tolerant
    deadline: str = ""
    action: str = ""


class DiagnosticReport(BaseModel):
    # Couche qualitative complète du pré-diagnostic. Affinable par l'analyste.
    model_config = _Tolerant

    summary: str = ""
    maturity: str | None = None
    maturity_rationale: str | None = None
    description: ReportDescription = Field(default_factory=ReportDescription)
    benchmark: list[str] = Field(default_factory=list)
    strengths: list[StrengthItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    competition: list[Competitor] = Field(default_factory=list)
    progress: ProgressMetrics = Field(default_factory=ProgressMetrics)
    verdict: Verdict = Field(default_factory=Verdict)
    recommendations: list[Recommendation] = Field(default_factory=list)
    next_steps: list[NextStep] = Field(default_factory=list)


class NextAction(BaseModel):
    # Action dérivée d'un axe faible → levier typé (intent, pas un lien : résolu par la feature).
    key: str  # dimension, ex. "d6"
    code: str = ""  # "D6"
    dimension: str  # libellé "Modèle économique"
    score: int
    severity: str  # "faible" | "moyen"
    lever_type: str  # academy | pitchsim | document | mentor
    topic: str | None = None
    label: str  # CTA porteur ("Apprends : modèle économique")
    primary: bool = False


class ReportOut(BaseModel):
    # Vue liste (dashboard porteur).
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    status: ReportStatus
    created_at: datetime


class ReportDetailOut(ReportOut):
    # Vue détail : score Radar + tableau de compréhension + rapport structuré.
    grid_version: str | None = None
    radar_score: RadarScore | None = None
    comprehension: dict | None = None
    report: DiagnosticReport | None = Field(default=None, validation_alias="insights")
    next_actions: list[NextAction] = Field(default_factory=list)

    @field_validator("next_actions", mode="before")
    @classmethod
    def _none_to_list(cls, value: object) -> object:
        # La colonne ORM peut être NULL → liste vide.
        return value or []


class PdfLink(BaseModel):
    # Lien de téléchargement presigned du PDF du bilan (expire ~24h).
    url: str


class ScoreAdjustIn(BaseModel):
    # Affinage humain des 12 dimensions (analyste/mentor). Produit un ScoreRun source=human.
    # Validé strictement contre la grille (bornes 0..scale_max + ancres) côté service.
    axes: dict[str, int]
    justifications: dict[str, str] | None = None
    grid_version: str | None = None  # par défaut : grille active
