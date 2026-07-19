"""Projection explicable : score, confiance, preuves et questions adaptatives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.project_memory.domain import effective_evidence_state, strongest_evidence_state
from app.project_memory.models import EvidenceState, MemoryItemType, ProjectMemoryItem
from app.project_memory.repository import ProjectMemoryRepository
from app.scoring.models import ScoreRun, ScoreSource


@dataclass(frozen=True)
class DimensionProjection:
    dimension: str
    code: str
    label: str
    pillar: str
    score: int | None
    confidence: float
    evidence_state: EvidenceState
    rationale: str
    contradictions: list[dict[str, str]]
    missing_information: str
    next_action: dict
    score_run_id: UUID | None
    evaluated_at: datetime | None


@dataclass(frozen=True)
class AdaptiveQuestion:
    dimension: str
    code: str
    label: str
    question: str
    reason: str
    priority: float


_EVIDENCE_GAP = {
    EvidenceState.UNKNOWN: 1.0,
    EvidenceState.INFERRED: 0.8,
    EvidenceState.DECLARED: 0.55,
    EvidenceState.SUPPORTED: 0.2,
    EvidenceState.VERIFIED: 0.0,
    EvidenceState.STALE: 0.9,
}


# Plafond de confiance d'une dimension dont les affirmations se contredisent (IDX-MEM-06).
#
# La confiance mesure normalement l'ACCORD ENTRE LES PASSES de scoring. Or trois passes peuvent
# s'accorder parfaitement sur un dossier qui se contredit lui-même : c'est exactement le défaut
# mesuré — un dossier auto-contradictoire ressortait à 96,6 % de confiance. L'accord entre passes
# ne dit rien de la cohérence du récit.
#
# On plafonne donc : on ne peut pas être sûr à plus de la moitié d'un axe dont les propres
# affirmations s'opposent. Valeur calée sous `EnsembleThresholds.min_confidence` (0,60) pour que
# la dimension bascule aussi du bon côté du routage vers la revue humaine.
#
# Le plafond ne se durcit PAS avec le nombre de contradictions : rien ne le justifierait par la
# mesure, et une contradiction suffit à disqualifier la certitude.
CONTRADICTION_CONFIDENCE_CAP = 0.5


def _axis_confidence(run: ScoreRun, dimension: str, *, scale_max: int) -> float:
    spread = (run.spread or {}).get(dimension)
    if spread is not None:
        return round(max(0.0, min(1.0, 1.0 - float(spread) / (scale_max * 0.5))), 3)
    if run.source is ScoreSource.HUMAN:
        return 0.9
    if run.confidence is not None:
        return round(max(0.0, min(1.0, run.confidence)), 3)
    return 0.5


def _action_for_dimension(next_actions: list, dimension: str) -> dict:
    for action in next_actions:
        if isinstance(action, dict) and action.get("key") == dimension:
            return dict(action)
    return {}


def build_dimension_projections(
    *,
    axes: list[dict[str, Any]],
    score_run: ScoreRun | None,
    memory_items: list[ProjectMemoryItem],
    next_actions: list | None = None,
    scale_max: int = 10,
    now: datetime | None = None,
) -> list[DimensionProjection]:
    """Construit une vue lisible sans jamais assimiler un score à une preuve."""
    next_actions = next_actions or []
    by_dimension: dict[str, list[ProjectMemoryItem]] = {}
    for item in memory_items:
        if item.is_active:
            by_dimension.setdefault(item.dimension, []).append(item)

    projections: list[DimensionProjection] = []
    for axis in axes:
        dimension = str(axis["key"])
        items = by_dimension.get(dimension, [])
        states = [effective_evidence_state(item.evidence_state, expires_at=item.expires_at, now=now) for item in items]
        evidence_state = strongest_evidence_state(states)
        score = score_run.axes.get(dimension) if score_run is not None else None
        if evidence_state is EvidenceState.UNKNOWN and score is not None:
            evidence_state = EvidenceState.INFERRED
        confidence = _axis_confidence(score_run, dimension, scale_max=scale_max) if score_run is not None else 0.0
        # Les DEUX citations accompagnent le constat : c'est ce qui le rend vérifiable en
        # quelques secondes. Sans elles, le porteur lirait une accusation sans preuve.
        # `attributes` est vide pour les contradictions saisies à la main : on n'ajoute donc
        # les clés que lorsqu'elles existent, pour ne pas polluer le contrat de chaînes vides.
        contradictions = [
            {
                "id": str(item.id),
                "statement": item.statement,
                **{
                    key: str(item.attributes[key])
                    for key in ("quote_a", "quote_b", "inconsistency_type", "severity")
                    if (item.attributes or {}).get(key)
                },
            }
            for item in items
            if item.item_type is MemoryItemType.CONTRADICTION
        ]
        # Un axe qui se contredit ne peut pas être tenu pour sûr, même si les passes de
        # scoring étaient unanimes : l'unanimité porte sur la lecture, pas sur la cohérence.
        if contradictions:
            confidence = min(confidence, CONTRADICTION_CONFIDENCE_CAP)
        guiding_questions = axis.get("guiding_questions") or []
        needs_clarification = (
            score is None
            or score <= 6
            or confidence < 0.6
            or evidence_state
            in {EvidenceState.UNKNOWN, EvidenceState.INFERRED, EvidenceState.DECLARED, EvidenceState.STALE}
            or bool(contradictions)
        )
        missing_information = str(guiding_questions[0]) if needs_clarification and guiding_questions else ""
        justifications = score_run.justifications or {} if score_run is not None else {}
        rationale = str(justifications.get(dimension, ""))
        projections.append(
            DimensionProjection(
                dimension=dimension,
                code=str(axis.get("code", dimension.upper())),
                label=str(axis.get("label", dimension)),
                pillar=str(axis.get("pillar", "")),
                score=score,
                confidence=confidence,
                evidence_state=evidence_state,
                rationale=rationale,
                contradictions=contradictions,
                missing_information=missing_information,
                next_action=_action_for_dimension(next_actions, dimension),
                score_run_id=score_run.id if score_run is not None else None,
                evaluated_at=score_run.created_at if score_run is not None else None,
            )
        )
    return projections


def select_adaptive_questions(
    projections: list[DimensionProjection],
    *,
    limit: int = 3,
) -> list[AdaptiveQuestion]:
    """Choisit les trois informations dont l'apport réduit le plus l'incertitude."""
    candidates: list[AdaptiveQuestion] = []
    for projection in projections:
        if not projection.missing_information:
            continue
        score_gap = 1.0 if projection.score is None else (10 - projection.score) / 10
        contradiction_gap = 0.5 if projection.contradictions else 0.0
        priority = round(
            score_gap + (1 - projection.confidence) + _EVIDENCE_GAP[projection.evidence_state] + contradiction_gap,
            3,
        )
        reason = "preuve insuffisante"
        if projection.contradictions:
            reason = "contradiction à éclaircir"
        elif projection.confidence < 0.6:
            reason = "évaluation incertaine"
        elif projection.score is None or projection.score <= 6:
            reason = "dimension à renforcer"
        candidates.append(
            AdaptiveQuestion(
                dimension=projection.dimension,
                code=projection.code,
                label=projection.label,
                question=projection.missing_information,
                reason=reason,
                priority=priority,
            )
        )
    return sorted(candidates, key=lambda question: (-question.priority, question.dimension))[:limit]


class ProjectEvaluationProjector:
    """Persiste la dernière projection tout en conservant les sources d'origine."""

    def __init__(self, memory: ProjectMemoryRepository) -> None:
        self.memory = memory

    async def persist_from_score_run(
        self,
        *,
        project_id: UUID,
        axes: list[dict[str, Any]],
        score_run: ScoreRun,
        next_actions: list | None,
        scale_max: int,
    ) -> list[DimensionProjection]:
        memory_items = await self.memory.list_for_project(project_id, active_only=True, limit=1000)
        projections = build_dimension_projections(
            axes=axes,
            score_run=score_run,
            memory_items=memory_items,
            next_actions=next_actions,
            scale_max=scale_max,
        )
        for projection in projections:
            await self.memory.upsert_dimension_state(
                project_id=project_id,
                dimension=projection.dimension,
                score=projection.score,
                confidence=projection.confidence,
                evidence_state=projection.evidence_state,
                rationale=projection.rationale,
                contradictions=projection.contradictions,
                missing_information=projection.missing_information,
                next_action=projection.next_action,
                last_score_run_id=projection.score_run_id,
                evaluated_at=projection.evaluated_at,
            )
        return projections
