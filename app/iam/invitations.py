"""Invitations admin & mentor — modèle.

Le service et les routes complètes arrivent au Sprint 5 (épic MENTOR/ADMIN). On pose
dès maintenant le MODÈLE pour que le schéma soit complet et migrable. Points durs
imposés (à respecter à l'implémentation) : token jamais stocké en clair, usage unique,
expiration stricte, audit des deux bouts (envoi + acceptation).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.iam.models import Role


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Invitation(Base):
    # Invitation nominative émise par un admin pour un mentor ou un autre admin.
    # Le token n'est jamais stocké en clair : on garde uniquement son hash.
    __tablename__ = "invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[Role]  # MENTOR ou ADMIN
    # Permissions pré-accordées à l'acceptation (ex. {certification:sign} pour créer
    # directement un mentor-certificateur plutôt qu'un simple coach).
    granted_permissions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    cv_document_id: Mapped[UUID | None] = mapped_column(default=None)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    status: Mapped[InvitationStatus] = mapped_column(default=InvitationStatus.PENDING)
    invited_by: Mapped[UUID]
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
