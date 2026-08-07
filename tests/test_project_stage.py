"""Vocabulaire canonique des étapes projet."""

from __future__ import annotations

from app.core.project_stage import ProjectStage
from app.diagnostics.schemas import ManualDiagnosticIn
from app.iam.models import ProjectStage as IamProjectStage
from app.projects.models import ProjectStage as ProjectModelStage


def test_one_project_stage_enum_is_shared_by_iam_and_projects() -> None:
    assert IamProjectStage is ProjectStage
    assert ProjectModelStage is ProjectStage
    assert [stage.value for stage in ProjectStage] == ["idea", "validation", "mvp", "traction", "scale"]


def test_legacy_api_stages_are_normalized() -> None:
    data = ManualDiagnosticIn(
        projectName="Projet test",
        sector="fintech",
        description="Une description suffisamment longue pour être validée.",
        consent=True,
        stage="prototype",
    )
    assert data.stage is ProjectStage.MVP
    assert ProjectStage("first_customers") is ProjectStage.TRACTION
    assert ProjectStage("growing") is ProjectStage.SCALE
