"""Modèles scoring — grille versionnée + ScoreRun (trace rejouable/auditable).

`ScoringGrid` = le référentiel (lentilles, axes ancrés, poids par catégorie), versionné.
`ScoreRun`    = une exécution de scoring : ce qu'on a donné, qui l'a produit (modèle ou
humain), la sortie brute, les axes validés et l'agrégation. C'est le socle de la
robustesse : tout score est **rejouable** et **auditable** (cf. `scoring-core-metier`).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScoringGrid(Base):
    __tablename__ = "scoring_grids"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    scale_max: Mapped[int] = mapped_column(default=10)  # /10 en v2 (/100 en v1)
    # Définition (JSONB, requêtable et versionnable) :
    #   pillars = [{key,label,question}]
    #   axes    = [{key,code,label,pillar,central_question, anchors:[{min,max,label}], guiding_questions:[...]}]
    #   category_weights = { catégorie: { dimKey: poids } }
    pillars: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    axes: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    category_weights: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ScoreSource(str, Enum):
    LLM = "llm"  # produit par un provider LLM
    HUMAN = "human"  # ajusté/posé par un analyste (regard humain)
    REPLAY = "replay"  # rejeu d'un run existant (régression/audit)


class ScoreRun(Base):
    # Une exécution de scoring, conservée pour rejeu, audit et calibration.
    __tablename__ = "score_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    diagnostic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="SET NULL"), index=True, default=None
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), index=True, default=None
    )

    # Reproductibilité : tout ce qui détermine un score est figé ici.
    grid_version: Mapped[str] = mapped_column(String(40), index=True)
    prompt_version: Mapped[str] = mapped_column(String(40), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[ScoreSource] = mapped_column(default=ScoreSource.LLM)

    # Audit : la sortie brute (LLM) telle quelle, pour rejeu et diagnostic de dérive.
    raw_output: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Résultat : axes validés sur l'échelle de la grille, justifications et agrégation.
    axes: Mapped[dict] = mapped_column(JSONB, default=dict)
    justifications: Mapped[dict | None] = mapped_column(JSONB, default=None)
    pillars: Mapped[dict] = mapped_column(JSONB, default=dict)  # scores agrégés par pilier
    overall: Mapped[int] = mapped_column(default=0)

    # Incertitude (ensemble) : N passes → consensus + confiance + étendue par axe.
    n_passes: Mapped[int] = mapped_column(default=1)
    confidence: Mapped[float | None] = mapped_column(default=None)
    spread: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Vrai si le score s'auto-déclare incertain → à router vers la revue analyste.
    needs_review: Mapped[bool] = mapped_column(default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
