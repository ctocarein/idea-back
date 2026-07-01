"""DTO Academy — leçons, progression, modules guidés, fiches de besoin."""

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


# --- Ancien Construire guidé (conservé pour compatibilité) ---


class GuidedStartIn(BaseModel):
    section: str = Field(min_length=1, max_length=80)
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


# --- Modules Academy (nouveaux) ---


class WeaknessOut(BaseModel):
    """Une dimension faible détectée par le Radar, avec contexte pour le porteur."""

    dimension: str          # d1..d12
    label: str              # "Modèle économique"
    score: int              # 0-10 — score EFFECTIF (re-mesuré si dispo, sinon radar)
    original_score: int     # 0-10 — score du bilan Radar initial
    central_question: str   # question directrice de la dimension
    pillar: str             # sens | viabilite | scalabilite | execution
    module_session_id: UUID | None = None   # session existante si module déjà démarré
    module_phase: str | None = None         # phase actuelle du module (context | form | fiches)
    is_reinforced: bool = False             # True quand les fiches ont été générées (axe renforcé)
    is_rescored: bool = False               # True quand l'axe a été re-mesuré après le module


class WeaknessListOut(BaseModel):
    weaknesses: list[WeaknessOut]
    dimensions_worked: int              # nombre de modules démarrés (context/form/fiches)
    dimensions_reinforced: int = 0      # nombre d'axes renforcés (fiches générées)
    reinforced_dimensions: list[str] = []  # clés d1..d12 des axes renforcés (pour le Radar)
    has_radar: bool                     # False si aucun bilan Radar disponible


class ModuleStartIn(BaseModel):
    dimension: str = Field(min_length=2, max_length=10)  # d1..d12
    project_id: UUID | None = None


class ModuleTurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ModuleFormIn(BaseModel):
    form_data: dict = Field(default_factory=dict)


class NeedFicheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dimension: str
    need_type: str
    title: str
    description: str
    details: dict
    is_validated: bool


class FicheShareOut(BaseModel):
    """Lien de partage d'une fiche (token en clair, retourné une fois à la création)."""

    token: str
    path: str  # ex. /shared/fiche/<token>


class SharedFicheOut(BaseModel):
    """Vue publique d'une fiche partagée — aucune donnée personnelle du porteur."""

    need_type: str
    title: str
    description: str
    details: dict
    project_title: str | None = None


class ModuleSessionOut(BaseModel):
    """Session de module avec contexte complet (conversation + formulaire + fiches)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dimension: str | None
    phase: str
    turns: list[dict]
    form_data: dict | None
    form_sections: list[dict] = Field(default_factory=list)    # fourni par le service (non stocké)
    fiches: list[NeedFicheOut] = Field(default_factory=list)   # fiches générées pour cette session
    context_ready: bool = False                                # le coach juge la conversation suffisante
    axis_score_before: int | None = None                       # score de l'axe avant le module
    axis_score_after: int | None = None                        # score re-mesuré après le module
