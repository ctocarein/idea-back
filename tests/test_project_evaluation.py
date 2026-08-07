"""Radar explicable : aucune confusion entre score, confiance et preuve."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.project_memory.evaluation import build_dimension_projections, select_adaptive_questions
from app.project_memory.models import EvidenceState, MemoryItemType
from app.scoring.models import ScoreSource


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        axes={"d1": 8, "d2": 3, "d3": 7, "d4": 6},
        spread={"d1": 0, "d2": 4, "d3": 1, "d4": 2},
        confidence=0.7,
        source=ScoreSource.LLM,
        justifications={"d1": "Le besoin est clairement décrit."},
        created_at=datetime(2026, 7, 16, tzinfo=UTC),
    )


def _axes() -> list[dict]:
    return [
        {
            "key": "d1",
            "code": "D1",
            "label": "Problème",
            "pillar": "sens",
            "guiding_questions": ["Qui souffre du problème ?"],
        },
        {
            "key": "d2",
            "code": "D2",
            "label": "Solution",
            "pillar": "sens",
            "guiding_questions": ["Comment la solution fonctionne-t-elle ?"],
        },
        {
            "key": "d3",
            "code": "D3",
            "label": "Valeur",
            "pillar": "sens",
            "guiding_questions": ["Quelle promesse unique ?"],
        },
        {
            "key": "d4",
            "code": "D4",
            "label": "Marché",
            "pillar": "viabilite",
            "guiding_questions": ["Quel marché cible ?"],
        },
        {
            "key": "d5",
            "code": "D5",
            "label": "Concurrence",
            "pillar": "viabilite",
            "guiding_questions": ["Quelles alternatives existent ?"],
        },
    ]


def _memory(*, dimension: str, state: EvidenceState, item_type: MemoryItemType = MemoryItemType.DECLARATION):
    return SimpleNamespace(
        id=uuid4(),
        dimension=dimension,
        evidence_state=state,
        item_type=item_type,
        statement="Élément de mémoire",
        expires_at=None,
        is_active=True,
        attributes={},  # comme le modèle réel (JSONB, default=dict)
    )


def test_high_score_declared_information_is_not_presented_as_verified() -> None:
    projections = build_dimension_projections(
        axes=_axes(),
        score_run=_run(),
        memory_items=[_memory(dimension="d1", state=EvidenceState.DECLARED)],
    )
    d1 = projections[0]

    assert d1.score == 8
    assert d1.confidence == 1.0
    assert d1.evidence_state is EvidenceState.DECLARED
    assert d1.missing_information == "Qui souffre du problème ?"
    assert d1.rationale == "Le besoin est clairement décrit."


def test_questions_prioritize_uncertain_weak_dimensions_and_never_exceed_three() -> None:
    projections = build_dimension_projections(
        axes=_axes(),
        score_run=_run(),
        memory_items=[
            _memory(dimension="d1", state=EvidenceState.SUPPORTED),
            _memory(dimension="d3", state=EvidenceState.VERIFIED),
            _memory(dimension="d4", state=EvidenceState.DECLARED, item_type=MemoryItemType.CONTRADICTION),
        ],
    )
    questions = select_adaptive_questions(projections)

    assert len(questions) == 3
    assert questions[0].dimension == "d2"
    assert questions[0].reason == "évaluation incertaine"
    assert {question.dimension for question in questions} == {"d2", "d4", "d5"}
