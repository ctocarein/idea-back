"""Règles du socle de mémoire projet et de provenance."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ValidationAppError
from app.project_memory.domain import (
    default_state_for_item,
    effective_evidence_state,
    ensure_dimension,
    strongest_evidence_state,
)
from app.project_memory.models import EvidenceState, MemoryItemType


@pytest.mark.parametrize("dimension", ["d1", "D2", " d12 "])
def test_dimension_is_normalized(dimension: str) -> None:
    assert ensure_dimension(dimension) in {"d1", "d2", "d12"}


@pytest.mark.parametrize("dimension", ["", "d0", "d13", "traction", "1"])
def test_unknown_dimension_is_rejected(dimension: str) -> None:
    with pytest.raises(ValidationAppError):
        ensure_dimension(dimension)


def test_memory_item_never_promotes_a_hypothesis_to_fact() -> None:
    assert default_state_for_item(MemoryItemType.HYPOTHESIS) is EvidenceState.INFERRED
    assert default_state_for_item(MemoryItemType.DECLARATION) is EvidenceState.DECLARED
    assert default_state_for_item(MemoryItemType.EVIDENCE) is EvidenceState.SUPPORTED
    assert default_state_for_item(MemoryItemType.DECISION) is EvidenceState.VERIFIED


def test_strongest_state_ignores_stale_items() -> None:
    assert (
        strongest_evidence_state([EvidenceState.DECLARED, EvidenceState.STALE, EvidenceState.SUPPORTED])
        is EvidenceState.SUPPORTED
    )
    assert strongest_evidence_state([EvidenceState.STALE]) is EvidenceState.UNKNOWN


def test_expired_evidence_is_effectively_stale() -> None:
    now = datetime(2026, 7, 16, tzinfo=UTC)
    assert (
        effective_evidence_state(
            EvidenceState.VERIFIED,
            expires_at=now - timedelta(seconds=1),
            now=now,
        )
        is EvidenceState.STALE
    )
    assert (
        effective_evidence_state(
            EvidenceState.SUPPORTED,
            expires_at=now + timedelta(days=1),
            now=now,
        )
        is EvidenceState.SUPPORTED
    )
