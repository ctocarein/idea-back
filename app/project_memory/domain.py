"""Règles déterministes de la mémoire projet et des états de preuve."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.core.errors import ValidationAppError
from app.project_memory.models import EvidenceState, MemoryItemType

DIMENSIONS = tuple(f"d{index}" for index in range(1, 13))

_EVIDENCE_STRENGTH = {
    EvidenceState.UNKNOWN: 0,
    EvidenceState.INFERRED: 1,
    EvidenceState.DECLARED: 2,
    EvidenceState.SUPPORTED: 3,
    EvidenceState.VERIFIED: 4,
}

_DEFAULT_STATE_BY_ITEM_TYPE = {
    MemoryItemType.HYPOTHESIS: EvidenceState.INFERRED,
    MemoryItemType.FACT: EvidenceState.DECLARED,
    MemoryItemType.DECLARATION: EvidenceState.DECLARED,
    MemoryItemType.CONTRADICTION: EvidenceState.DECLARED,
    MemoryItemType.EVIDENCE: EvidenceState.SUPPORTED,
    MemoryItemType.DECISION: EvidenceState.VERIFIED,
}


def ensure_dimension(dimension: str) -> str:
    """Valide la clé canonique d1..d12 sans accepter d'alias silencieux."""
    normalized = dimension.strip().lower()
    if normalized not in DIMENSIONS:
        raise ValidationAppError(
            "Dimension Radar invalide.",
            details=[{"dimension": dimension, "allowed": list(DIMENSIONS)}],
        )
    return normalized


def default_state_for_item(item_type: MemoryItemType) -> EvidenceState:
    """Retourne l'état initial prudent associé à la nature d'une information."""
    return _DEFAULT_STATE_BY_ITEM_TYPE[item_type]


def strongest_evidence_state(states: Iterable[EvidenceState]) -> EvidenceState:
    """Agrège des preuves actives sans confondre ancienneté et niveau de preuve."""
    usable = [state for state in states if state is not EvidenceState.STALE]
    if not usable:
        return EvidenceState.UNKNOWN
    return max(usable, key=lambda state: _EVIDENCE_STRENGTH[state])


def effective_evidence_state(
    state: EvidenceState,
    *,
    expires_at: datetime | None,
    now: datetime | None = None,
) -> EvidenceState:
    """Transforme une preuve expirée en `stale` sans réécrire son historique."""
    if state is EvidenceState.STALE or expires_at is None:
        return state
    reference = now or datetime.now(UTC)
    return EvidenceState.STALE if expires_at <= reference else state
