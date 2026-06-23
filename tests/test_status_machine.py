"""Tests des DEUX machines à états projet (réconciliation Sprint 2)."""

from __future__ import annotations

from app.projects.models import (
    DiagnosticStatus,
    ReviewStatus,
    can_transition_diagnostic,
    can_transition_review,
)

# --- Pipeline diagnostic (automatique) ---


def test_legal_diagnostic_pipeline() -> None:
    assert can_transition_diagnostic(DiagnosticStatus.DRAFT, DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS)
    assert can_transition_diagnostic(DiagnosticStatus.DIAGNOSTIC_IN_PROGRESS, DiagnosticStatus.DIAGNOSTIC_COMPLETED)
    assert can_transition_diagnostic(DiagnosticStatus.DIAGNOSTIC_COMPLETED, DiagnosticStatus.BILAN_READY)


def test_illegal_diagnostic_pipeline() -> None:
    # Sauter le diagnostic est interdit.
    assert not can_transition_diagnostic(DiagnosticStatus.DRAFT, DiagnosticStatus.BILAN_READY)
    # Un état terminal n'a pas de sortie.
    assert not can_transition_diagnostic(DiagnosticStatus.ARCHIVED, DiagnosticStatus.DRAFT)


# --- Curation humaine (analyste/admin) ---


def test_legal_review_curation() -> None:
    assert can_transition_review(ReviewStatus.NEW_DIAGNOSTIC, ReviewStatus.IN_REVIEW)
    assert can_transition_review(ReviewStatus.IN_REVIEW, ReviewStatus.QUALIFIED)
    assert can_transition_review(ReviewStatus.QUALIFIED, ReviewStatus.EXCELLENCE)
    # Un projet à retravailler peut repartir en analyse.
    assert can_transition_review(ReviewStatus.NEEDS_WORK, ReviewStatus.IN_REVIEW)


def test_illegal_review_curation() -> None:
    # On ne qualifie pas un projet qui n'a pas été mis en analyse.
    assert not can_transition_review(ReviewStatus.NEW_DIAGNOSTIC, ReviewStatus.QUALIFIED)
    # Pas de passage direct à l'excellence depuis l'analyse.
    assert not can_transition_review(ReviewStatus.IN_REVIEW, ReviewStatus.EXCELLENCE)


def test_two_machines_are_independent() -> None:
    # Les deux axes ne partagent aucune valeur.
    diagnostic_values = {s.value for s in DiagnosticStatus}
    review_values = {s.value for s in ReviewStatus}
    assert diagnostic_values.isdisjoint(review_values)
