"""Modèle document — métadonnées en base, octets dans MinIO.

Flux presigned : l'API émet une URL d'upload (PUT direct client→MinIO), puis confirme.
Elle ne transporte jamais le fichier ; elle ne garde que les métadonnées + la clé objet.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentStatus(str, Enum):
    PENDING = "pending"  # URL émise, upload pas encore confirmé
    CONFIRMED = "confirmed"  # le client a confirmé l'upload


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int]  # octets
    object_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[DocumentStatus] = mapped_column(default=DocumentStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
