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


# --- « Raconte, on structure » : extraction du récit libre → 12 dimensions ---


class IdeaExtractIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    # Le récit brut du porteur (texte ou dictée). Le nom est optionnel — on le déduit sinon.
    idea: str = Field(min_length=20, max_length=5000)
    project_name: str | None = Field(
        default=None, max_length=120, validation_alias=AliasChoices("project_name", "projectName")
    )
    # SEC-12 : consentement explicite requis avant envoi au LLM (données potentiellement sensibles).
    consent: bool = False

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Le consentement au traitement est requis pour analyser votre idée.")
        return value


class ExtractedDimension(BaseModel):
    key: str  # d1..d12
    label: str
    captured: bool  # le récit donne assez d'info ?
    evidence: str = ""  # preuve tirée du récit (si captured)
    question: str = ""  # question courte à poser (si manquant)


class IdeaExtractOut(BaseModel):
    project_name: str | None = None  # déduit du récit si non fourni
    captured_count: int
    total: int
    dimensions: list[ExtractedDimension]
    gaps: list[ExtractedDimension]  # les dimensions à compléter (captured=false)
    # Texte source utilisé pour l'extraction (récit brut ou texte extrait du fichier).
    # Renvoyé au front pour constituer le `description` du payload de scoring.
    source_text: str = ""
