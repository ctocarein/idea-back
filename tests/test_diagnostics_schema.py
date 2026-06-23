"""Tests de réconciliation des DTO diagnostic (alias front ↔ canonique backend)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.diagnostics.schemas import ManualDiagnosticIn
from app.projects.models import Archetype


def _front_payload(**overrides: object) -> dict[str, object]:
    # Payload tel que l'envoie le front actuel (camelCase + "terrain" + consent).
    base = {
        "projectName": "Ma startup",
        "sector": "agritech",
        "description": "Un projet qui résout un vrai problème agricole local.",
        "fundingNeed": "5000000",
        "consent": True,
        "archetype": "terrain",
    }
    base.update(overrides)
    return base


def test_accepts_front_camelcase_and_terrain_alias() -> None:
    dto = ManualDiagnosticIn.model_validate(_front_payload())
    assert dto.project_name == "Ma startup"  # projectName → project_name
    assert dto.archetype is Archetype.FIELD  # "terrain" → field
    assert dto.funding_need == 5_000_000  # string → int


def test_accepts_canonical_snake_case() -> None:
    dto = ManualDiagnosticIn.model_validate(
        {
            "project_name": "Projet",
            "sector": "fintech",
            "description": "Description suffisamment longue pour passer la validation.",
            "consent": True,
        }
    )
    assert dto.project_name == "Projet"
    assert dto.archetype is Archetype.FIELD  # défaut
    assert dto.funding_need is None


def test_consent_required() -> None:
    with pytest.raises(ValidationError):
        ManualDiagnosticIn.model_validate(_front_payload(consent=False))


def test_empty_funding_need_becomes_none() -> None:
    dto = ManualDiagnosticIn.model_validate(_front_payload(fundingNeed=""))
    assert dto.funding_need is None


def test_short_description_rejected() -> None:
    with pytest.raises(ValidationError):
        ManualDiagnosticIn.model_validate(_front_payload(description="trop court"))
