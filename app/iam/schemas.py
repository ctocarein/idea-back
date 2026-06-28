"""DTO Pydantic IAM — entrée/sortie. On n'expose jamais l'ORM directement."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.iam.models import AccountStatus, ProfessionalStatus, ProjectStage, Role, WeeklyAvailability


class RegisterIn(BaseModel):
    # populate_by_name : le champ canonique reste `full_name` (exposé dans l'OpenAPI),
    # mais on accepte aussi l'alias `name` envoyé par le front actuel → réconciliation
    # sans friction le temps que le front régénère ses types depuis l'OpenAPI.
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(
        min_length=2,
        max_length=200,
        validation_alias=AliasChoices("full_name", "name"),
    )
    # Consentement RGPD : miroir du `registerSchema` front (z.literal(true)).
    # Une inscription sans consentement est refusée (400).
    consent: bool = False

    @field_validator("consent")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Consentement requis (RGPD).")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    # Réponse d'authentification : access (court) + refresh (rotatif).
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: Role
    status: AccountStatus
    created_at: datetime
    # Profil porteur (None si onboarding pas encore complété).
    country: str | None = None
    city: str | None = None
    professional_status: ProfessionalStatus | None = None
    project_stage: ProjectStage | None = None
    weekly_availability: WeeklyAvailability | None = None
    onboarding_completed: bool = False


class UpdateMeIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)


class OnboardingIn(BaseModel):
    country: str = Field(min_length=2, max_length=2, description="Code ISO 3166-1 alpha-2")
    city: str | None = Field(default=None, max_length=100)
    professional_status: ProfessionalStatus
    project_stage: ProjectStage
    weekly_availability: WeeklyAvailability | None = None


class MeOut(BaseModel):
    # /auth/me : l'utilisateur + ses permissions effectives (pour piloter l'UX front).
    user: UserOut
    permissions: list[str]
