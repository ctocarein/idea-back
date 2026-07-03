"""Modèles d'identité — User, PermissionGrant, RefreshToken.

Modèle hybride : rôle (droits par défaut) + permissions explicites (capacités fines)
+ garde-fous au niveau ressource (cf. dependencies.py).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProfessionalStatus(str, Enum):
    STUDENT = "student"
    EMPLOYEE = "employee"
    ENTREPRENEUR = "entrepreneur"
    FREELANCE = "freelance"
    CAREER_CHANGE = "career_change"
    UNEMPLOYED = "unemployed"


class ProjectStage(str, Enum):
    IDEA = "idea"
    VALIDATION = "validation"
    MVP = "mvp"
    TRACTION = "traction"
    SCALE = "scale"


class WeeklyAvailability(str, Enum):
    LT5 = "lt5"
    H5_10 = "h5_10"
    H10_20 = "h10_20"
    GT20 = "gt20"


class Role(str, Enum):
    # Quatre rôles de premier niveau. "founder" = le porteur de projet.
    # "analyst" est le regard humain (souvent fondu dans l'admin) ; "investor" est
    # préparé mais inactif au MVP (côté investisseur = concierge manuel).
    ADMIN = "admin"
    MENTOR = "mentor"
    ANALYST = "analyst"
    INVESTOR = "investor"
    FOUNDER = "founder"


class AccountStatus(str, Enum):
    PENDING_REVIEW = "pending_review"  # auto-inscrit, en attente de validation admin
    INVITED = "invited"  # invité, pas encore activé (token non consommé)
    ACTIVE = "active"
    SUSPENDED = "suspended"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str]  # argon2id, jamais en clair
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role]  # rôle principal
    status: Mapped[AccountStatus] = mapped_column(default=AccountStatus.ACTIVE)
    # Preuve de possession de l'email (soft gate) : l'accès reste ouvert (conversion),
    # on prouve juste l'email pour la confiance / les actions sensibles.
    email_verified: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Langue préférée (ISO 639-1 : "fr" | "en"). Pilote l'UI ET le contenu généré par
    # l'IA (bilan, coach, deck) + les emails. Défaut "fr" (marché actuel).
    language: Mapped[str] = mapped_column(String(2), default="fr", server_default="fr")
    # Horodatage du consentement RGPD donné à l'inscription. Nullable : les comptes
    # créés autrement (seed, invitation) le renseignent à leur propre étape.
    consent_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Profil porteur (renseigné à l'onboarding post-inscription).
    country: Mapped[str | None] = mapped_column(String(2), default=None)  # ISO 3166-1 alpha-2
    city: Mapped[str | None] = mapped_column(String(100), default=None)
    professional_status: Mapped[ProfessionalStatus | None] = mapped_column(String(30), default=None)
    project_stage: Mapped[ProjectStage | None] = mapped_column(String(20), default=None)
    weekly_availability: Mapped[WeeklyAvailability | None] = mapped_column(String(10), default=None)
    onboarding_completed: Mapped[bool] = mapped_column(default=False)

    grants: Mapped[list[PermissionGrant]] = relationship(back_populates="user", cascade="all, delete-orphan")


class PermissionGrant(Base):
    # Permission accordée explicitement à un utilisateur, EN PLUS de celles de son rôle.
    # C'est le mécanisme qui transforme un "mentor" en "mentor-certificateur" :
    # on lui accorde la permission certification:sign, sans changer son rôle.
    __tablename__ = "permission_grants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    permission: Mapped[str]  # ex. "certification:sign"
    granted_by: Mapped[UUID]  # admin qui a accordé
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="grants")


class RefreshToken(Base):
    # Refresh token opaque, rotatif. On ne stocke que le HASH du token.
    # La réutilisation d'un token déjà consommé révoque toute la chaîne (détection de vol).
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    revoked: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
