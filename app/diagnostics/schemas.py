"""DTO diagnostics — réconciliés avec le front.

Réconciliation : le front envoie du camelCase (`projectName`, `fundingNeed`) et la valeur
`terrain` pour l'archétype. On accepte ces alias en entrée (canonique snake_case / `field`),
le temps que le front régénère ses types depuis l'OpenAPI. `consent` RGPD requis.
`archetype`/`stage` sont optionnels (défaut field/idea) : l'admin les ajuste ensuite.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.diagnostics.models import EntryMode
from app.projects.models import Archetype, DiagnosticStatus, ProjectStage, ReviewStatus


class _BaseDiagnosticIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_name: str = Field(
        min_length=2,
        max_length=200,
        validation_alias=AliasChoices("project_name", "projectName"),
    )
    # "sector" porte la clé de catégorie (agritech, fintech…), comme côté front.
    sector: str = Field(min_length=1, max_length=120)
    consent: bool = False
    archetype: Archetype = Archetype.FIELD
    stage: ProjectStage = ProjectStage.IDEA

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Consentement requis (RGPD).")
        return value

    @field_validator("archetype", mode="before")
    @classmethod
    def _normalize_archetype(cls, value: object) -> object:
        # Accepte l'alias front "terrain" → valeur canonique "field".
        if isinstance(value, str) and value.lower() == "terrain":
            return Archetype.FIELD.value
        return value


class ManualDiagnosticIn(_BaseDiagnosticIn):
    # Flow A — idée guidée.
    description: str = Field(min_length=20, max_length=5000)
    funding_need: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("funding_need", "fundingNeed"),
    )
    # Réponses aux questions par catégorie : { questionId: réponse }.
    answers: dict[str, str] | None = None

    @field_validator("funding_need", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        # Le front envoie une chaîne ("" si vide) → on normalise.
        if value in ("", None):
            return None
        return value


class UploadDiagnosticIn(_BaseDiagnosticIn):
    # Flow B — document uploadé (déjà confirmé via app/documents).
    document_id: UUID = Field(validation_alias=AliasChoices("document_id", "documentId"))


class DiagnosticCreatedOut(BaseModel):
    # Réponse 202 : le diagnostic est lancé, le bilan se génère en asynchrone.
    diagnostic_id: UUID
    project_id: UUID
    report_id: UUID
    mode: EntryMode
    diagnostic_status: DiagnosticStatus
    review_status: ReviewStatus
